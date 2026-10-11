"""Domain policy engine with trie-based lookup for MiniSWG."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any
import argparse


def _normalize_host(host: str) -> list[str]:
    """Normalize a hostname/domain and split into labels.

    Handles:
    - Stripping surrounding whitespace
    - Case-insensitivity (converts to lowercase)
    - Stripping port if present in host (e.g. 'host:8080' or '[::1]:8080')
    - Stripping trailing dot (DNS root zone notation, e.g. 'evil.com.')
    """
    if not host or not isinstance(host, str):
        return []

    host = host.strip().lower()

    # Strip scheme if present (e.g. 'https://' or 'http://')
    if "://" in host:
        host = host.split("://", 1)[1]

    # Strip path if present (e.g. 'evil.example/login')
    if "/" in host:
        host = host.split("/", 1)[0]

    # Strip port if present
    if host.startswith("[") and "]" in host:
        end = host.find("]")
        host = host[1:end]
    elif ":" in host and host.count(":") == 1:
        host = host.split(":", 1)[0]

    # Strip trailing dot (FQDN root notation)
    host = host.rstrip(".")
    if not host:
        return []

    return [label for label in host.split(".") if label]


class TrieNode:
    """A single node in the DomainTrie."""

    def __init__(self) -> None:
        self.children: dict[str, TrieNode] = {}
        self.category: str | None = None

    def __repr__(self) -> str:
        return f"TrieNode(category={self.category!r}, children={list(self.children.keys())})"


class DomainTrie:
    """Domain trie storing domains as reversed labels.

    For example:
    - 'evil.com' is stored as: root -> 'com' -> 'evil' (category set on 'evil')
    - '*.evil.com' is stored as: root -> 'com' -> 'evil' -> '*' (category set on '*')

    Supports exact and wildcard matching:
    - 'evil.com' matches exactly.
    - '*.evil.com' matches any subdomain (e.g., 'sub.evil.com', 'a.b.evil.com'),
      but does NOT match the bare parent ('evil.com') unless explicitly specified.
    - Lookup time complexity is O(number of labels).
    """

    def __init__(self, rules: dict[str, str] | None = None) -> None:
        self.root = TrieNode()
        if rules:
            for domain, category in rules.items():
                self.insert(domain, category)

    def insert(self, domain: str, category: str) -> None:
        """Insert a domain rule with an associated category.

        Labels are stored in reversed order (TLD first, then domain, then subdomains/wildcards).
        """
        labels = _normalize_host(domain)
        if not labels:
            return

        curr = self.root
        for label in reversed(labels):
            if label not in curr.children:
                curr.children[label] = TrieNode()
            curr = curr.children[label]

        curr.category = category

    def lookup(self, host: str) -> str | None:
        """Look up the category for a given host.

        Traverses the trie matching reversed labels.
        At each level, if a wildcard child ('*') exists, it is recorded as a candidate match.
        If the full host path matches an exact category, the exact category is returned.
        Otherwise, the most specific matching wildcard category is returned.
        If no rule matches, returns None.

        Complexity is O(number of labels).
        """
        labels = _normalize_host(host)
        if not labels:
            return None

        curr = self.root
        wildcard_category: str | None = None

        for label in reversed(labels):
            # If current node has a wildcard child, any subdomain under this node matches.
            # Record it as the latest (most specific) wildcard match candidate.
            if "*" in curr.children and curr.children["*"].category is not None:
                wildcard_category = curr.children["*"].category

            if label not in curr.children:
                return wildcard_category

            curr = curr.children[label]

        # Reached the exact node matching all labels of the host
        if curr.category is not None:
            return curr.category

        # Bare parent doesn't match wildcard at this node unless wildcard was recorded earlier
        return wildcard_category

    def __contains__(self, host: str) -> bool:
        return self.lookup(host) is not None


@dataclass
class Decision:
    """Result of policy evaluation for a target host."""

    action: str  # "allow" | "block"
    reason: str  # "allowlist" | "blocked_category" | "default_allow"
    category: str | None = None

    def __iter__(self):
        yield self.action
        yield self.reason
        yield self.category


class Policy:
    """Policy engine that evaluates requests against allowlist, categories, and blocklists.

    Decision order:
    1. allowlist first -> action="allow", reason="allowlist"
    2. blocked category check -> action="block", reason="blocked_category"
    3. default allow -> action="allow", reason="default_allow"
    """

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        *,
        blocked_categories: list[str] | None = None,
        categories: dict[str, list[str]] | None = None,
        allowlist: list[str] | None = None,
        rate_limit: dict[str, Any] | None = None,
    ) -> None:
        data = data or {}

        # 1. Blocked categories
        raw_blocked = blocked_categories if blocked_categories is not None else data.get("blocked_categories", [])
        self.blocked_categories: set[str] = set(raw_blocked)

        # 2. Categories mapping: category_name -> list of domains
        raw_categories = categories if categories is not None else data.get("categories", {})
        self.categories: dict[str, list[str]] = raw_categories

        # 3. Allowlist
        raw_allowlist = allowlist if allowlist is not None else data.get("allowlist", [])
        if isinstance(raw_allowlist, str):
            raw_allowlist = [raw_allowlist]
        self.allowlist: list[str] = list(raw_allowlist)

        # 4. Rate limit settings
        self.rate_limit: dict[str, Any] = rate_limit if rate_limit is not None else data.get("rate_limit", {})

        # Build tries
        self.trie = DomainTrie()
        for cat, domains in self.categories.items():
            if isinstance(domains, str):
                domains = [domains]
            for domain in domains:
                self.trie.insert(domain, cat)

        self.allowlist_trie = DomainTrie()
        for domain in self.allowlist:
            self.allowlist_trie.insert(domain, "allowlist")

    def evaluate(self, host: str) -> Decision:
        """Evaluate a host according to policy rules.

        Decision order:
        1. Allowlist check
        2. Blocked category check
        3. Default allow
        """
        category = self.trie.lookup(host)

        # 1. Allowlist first
        if self.allowlist_trie.lookup(host) is not None:
            return Decision(action="allow", reason="allowlist", category=category)

        # 2. Blocked category check
        if category is not None and category in self.blocked_categories:
            return Decision(action="block", reason="blocked_category", category=category)

        # 3. Default allow
        return Decision(action="allow", reason="default_allow", category=category)

    # Convenience aliases
    def decide(self, host: str) -> Decision:
        return self.evaluate(host)

    def check(self, host: str) -> Decision:
        return self.evaluate(host)

    def lookup(self, host: str) -> Decision:
        return self.evaluate(host)

    def __call__(self, host: str) -> Decision:
        return self.evaluate(host)

    @classmethod
    def from_file(cls, filepath: str | Path) -> "Policy":
        return load_policy(filepath)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Policy":
        return cls(data)


PolicyEngine = Policy


def load_policy(source: str | Path | dict | None = None) -> Policy:
    """Load policy from a JSON file path or a dictionary.

    Defaults to 'config/policy.json' if source is None.
    """
    if source is None:
        source = "config/policy.json"

    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Policy(data)
    elif isinstance(source, dict):
        return Policy(source)
    else:
        raise TypeError(f"Invalid policy source type: {type(source)}")


def parse_args(args=None):
    """Parse CLI arguments for policy selection."""
    parser = argparse.ArgumentParser(description="MiniSWG Policy Engine")
    parser.add_argument(
        "--policy",
        default="config/policy.json",
        help="Path to policy JSON file (default: config/policy.json)",
    )
    parser.add_argument(
        "--host",
        help="Optional host to evaluate against policy",
    )
    return parser.parse_args(args)


if __name__ == "__main__":
    cli_args = parse_args()
    loaded_policy = load_policy(cli_args.policy)
    print(f"Loaded policy from: {cli_args.policy}")
    print(f"Blocked categories: {loaded_policy.blocked_categories}")
    print(f"Allowlisted domains: {loaded_policy.allowlist}")
    if cli_args.host:
        res = loaded_policy.evaluate(cli_args.host)
        print(f"Decision for '{cli_args.host}': action={res.action}, reason={res.reason}, category={res.category}")
