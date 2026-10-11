import pytest
from miniswg.policy import (
    DomainTrie,
    TrieNode,
    Decision,
    Policy,
    PolicyEngine,
    load_policy,
    parse_args as parse_policy_args,
)
from miniswg.proxy import (
    parse_args as parse_proxy_args,
    set_policy,
    get_policy,
    handle_client_inner,
)


def test_exact_match():
    trie = DomainTrie()
    trie.insert("evil.com", "malware")
    trie.insert("bank.com", "finance")

    assert trie.lookup("evil.com") == "malware"
    assert trie.lookup("bank.com") == "finance"


def test_wildcard_match():
    trie = DomainTrie()
    trie.insert("*.evil.com", "malware")

    # Single-level subdomain
    assert trie.lookup("sub.evil.com") == "malware"
    assert trie.lookup("bad.evil.com") == "malware"

    # Multi-level subdomains (any subdomain)
    assert trie.lookup("deep.sub.evil.com") == "malware"
    assert trie.lookup("a.b.c.d.evil.com") == "malware"


def test_no_match():
    trie = DomainTrie()
    assert trie.lookup("example.com") is None

    trie.insert("evil.com", "malware")
    trie.insert("*.badsite.org", "phishing")

    # Completely unrelated domains
    assert trie.lookup("google.com") is None
    assert trie.lookup("badsite.com") is None
    assert trie.lookup("evil.org") is None

    # Partial / substring match should not match
    assert trie.lookup("notevil.com") is None
    assert trie.lookup("evil.com.attacker.com") is None


def test_wildcard_does_not_match_bare_parent_unless_specified():
    trie = DomainTrie()
    trie.insert("*.evil.com", "malware")

    # Bare parent must NOT match the wildcard rule
    assert trie.lookup("evil.com") is None

    # Any subdomain still matches
    assert trie.lookup("test.evil.com") == "malware"

    # When bare parent is explicitly specified, it now matches
    trie.insert("evil.com", "malware-parent")
    assert trie.lookup("evil.com") == "malware-parent"
    assert trie.lookup("test.evil.com") == "malware"


def test_case_insensitivity():
    trie = DomainTrie()
    trie.insert("EvIL.CoM", "malware")
    trie.insert("*.BaD-SiTe.Org", "phishing")

    # Lookup with various cases
    assert trie.lookup("evil.com") == "malware"
    assert trie.lookup("EVIL.COM") == "malware"
    assert trie.lookup("Evil.Com") == "malware"

    assert trie.lookup("sub.bad-site.org") == "phishing"
    assert trie.lookup("SUB.BAD-SITE.ORG") == "phishing"
    assert trie.lookup("Sub.BaD-SiTe.Org") == "phishing"


def test_trailing_dot():
    trie = DomainTrie()
    trie.insert("evil.com.", "malware")
    trie.insert("*.badsite.com", "phishing")

    # Inserted with trailing dot, queried without
    assert trie.lookup("evil.com") == "malware"
    # Inserted with trailing dot, queried with trailing dot
    assert trie.lookup("evil.com.") == "malware"

    # Inserted without trailing dot, queried with trailing dot
    assert trie.lookup("sub.badsite.com.") == "phishing"
    assert trie.lookup("deep.sub.badsite.com.") == "phishing"


def test_exact_overrides_wildcard():
    trie = DomainTrie()
    trie.insert("*.evil.com", "malware")
    trie.insert("safe.evil.com", "allow")

    assert trie.lookup("safe.evil.com") == "allow"
    assert trie.lookup("other.evil.com") == "malware"


def test_more_specific_wildcard_overrides_broader_wildcard():
    trie = DomainTrie()
    trie.insert("*.evil.com", "general-bad")
    trie.insert("*.phish.evil.com", "phishing")

    assert trie.lookup("login.phish.evil.com") == "phishing"
    assert trie.lookup("deep.login.phish.evil.com") == "phishing"
    assert trie.lookup("other.evil.com") == "general-bad"
    # Bare parent of the more specific wildcard falls back to the broader wildcard
    assert trie.lookup("phish.evil.com") == "general-bad"


def test_internal_reversed_labels_trie_structure():
    trie = DomainTrie()
    trie.insert("*.badsite.com", "malware")
    trie.insert("badsite.com", "phishing")

    # Verify root has 'com'
    assert "com" in trie.root.children
    node_com = trie.root.children["com"]
    assert node_com.category is None

    # Verify 'com' has child 'badsite'
    assert "badsite" in node_com.children
    node_badsite = node_com.children["badsite"]
    assert node_badsite.category == "phishing"

    # Verify 'badsite' has child '*'
    assert "*" in node_badsite.children
    node_star = node_badsite.children["*"]
    assert node_star.category == "malware"


def test_empty_and_invalid_inputs():
    trie = DomainTrie()
    trie.insert("evil.com", "malware")

    assert trie.lookup("") is None
    assert trie.lookup(".") is None
    assert trie.lookup("...") is None
    assert trie.lookup(None) is None
    assert trie.lookup("   ") is None


def test_host_with_port():
    trie = DomainTrie()
    trie.insert("evil.com", "malware")
    trie.insert("*.badsite.com", "phishing")

    assert trie.lookup("evil.com:80") == "malware"
    assert trie.lookup("evil.com:443") == "malware"
    assert trie.lookup("sub.badsite.com:8080") == "phishing"


def test_contains_operator():
    trie = DomainTrie({"evil.com": "malware", "*.badsite.com": "phishing"})

    assert "evil.com" in trie
    assert "sub.badsite.com" in trie
    assert "google.com" not in trie
    assert "badsite.com" not in trie


def test_load_policy_from_config_file():
    policy = load_policy("config/policy.json")

    assert policy.blocked_categories == {"malware", "gambling"}
    assert "malware" in policy.categories
    assert "*.badsite.com" in policy.categories["malware"]
    assert "evil.example" in policy.categories["malware"]
    assert "*.casino.com" in policy.categories["gambling"]
    assert "*.facebook.com" in policy.categories["social"]
    assert policy.allowlist == ["internal.company.com"]
    assert policy.rate_limit["requests_per_minute"] == 120
    assert policy.rate_limit["burst"] == 20


def test_decision_order_allowlist_first():
    policy = load_policy("config/policy.json")

    # Allowlisted domain
    decision = policy.evaluate("internal.company.com")
    assert decision.action == "allow"
    assert decision.reason == "allowlist"
    assert decision.category is None

    # Trailing dot and case-insensitivity on allowlist
    assert policy.evaluate("INTERNAL.COMPANY.COM").action == "allow"
    assert policy.evaluate("internal.company.com.").action == "allow"


def test_allowlist_precedence_over_blocked_categories():
    # If a domain is in both allowlist and blocked categories, allowlist must win
    custom_policy = Policy({
        "blocked_categories": ["malware"],
        "categories": {"malware": ["*.company.com", "danger.com"]},
        "allowlist": ["safe.company.com", "danger.com"]
    })

    d1 = custom_policy.evaluate("safe.company.com")
    assert d1.action == "allow"
    assert d1.reason == "allowlist"

    d2 = custom_policy.evaluate("danger.com")
    assert d2.action == "allow"
    assert d2.reason == "allowlist"

    # Other subdomain not on allowlist should still be blocked
    d3 = custom_policy.evaluate("other.company.com")
    assert d3.action == "block"
    assert d3.reason == "blocked_category"
    assert d3.category == "malware"


def test_decision_order_blocked_category_check():
    policy = load_policy("config/policy.json")

    # Exact malware match
    d1 = policy.evaluate("evil.example")
    assert d1.action == "block"
    assert d1.reason == "blocked_category"
    assert d1.category == "malware"

    # Wildcard malware match
    d2 = policy.evaluate("test.badsite.com")
    assert d2.action == "block"
    assert d2.reason == "blocked_category"
    assert d2.category == "malware"

    # Deep wildcard malware match
    d3 = policy.evaluate("deep.sub.badsite.com")
    assert d3.action == "block"
    assert d3.reason == "blocked_category"
    assert d3.category == "malware"

    # Wildcard gambling match
    d4 = policy.evaluate("poker.casino.com")
    assert d4.action == "block"
    assert d4.reason == "blocked_category"
    assert d4.category == "gambling"


def test_decision_order_default_allow():
    policy = load_policy("config/policy.json")

    # Domain in category 'social', but 'social' is NOT in blocked_categories
    d1 = policy.evaluate("m.facebook.com")
    assert d1.action == "allow"
    assert d1.reason == "default_allow"
    assert d1.category == "social"

    # Uncategorized domain not present in policy
    d2 = policy.evaluate("wikipedia.org")
    assert d2.action == "allow"
    assert d2.reason == "default_allow"
    assert d2.category is None


def test_decision_object_attributes_and_unpacking():
    d = Decision(action="block", reason="blocked_category", category="malware")
    assert d.action == "block"
    assert d.reason == "blocked_category"
    assert d.category == "malware"

    # Supports tuple-style unpacking
    action, reason, category = d
    assert action == "block"
    assert reason == "blocked_category"
    assert category == "malware"


def test_cli_flag_policy(tmp_path):
    # Test policy CLI parsing
    args = parse_policy_args(["--policy", "custom_policy.json"])
    assert args.policy == "custom_policy.json"

    default_policy_args = parse_policy_args([])
    assert default_policy_args.policy == "config/policy.json"

    # Test proxy CLI parsing
    proxy_args = parse_proxy_args(["--policy", "another_policy.json", "--port", "9090"])
    assert proxy_args.policy == "another_policy.json"
    assert proxy_args.port == 9090

    default_proxy_args = parse_proxy_args([])
    assert default_proxy_args.policy == "config/policy.json"

    # Test loading custom policy file created dynamically
    custom_file = tmp_path / "custom.json"
    custom_file.write_text('{"blocked_categories": ["phishing"], "categories": {"phishing": ["phish.net"]}}')
    custom_pol = load_policy(str(custom_file))
    assert custom_pol.evaluate("phish.net").action == "block"


@pytest.mark.asyncio
async def test_proxy_blocks_request_via_policy():
    import asyncio

    # Setup active policy
    policy = load_policy("config/policy.json")
    set_policy(policy)

    class MockWriter:
        def __init__(self):
            self.data = bytearray()
            self.closed = False

        def get_extra_info(self, name):
            return ("127.0.0.1", 12345)

        def write(self, b):
            self.data.extend(b)

        async def drain(self):
            pass

        def close(self):
            self.closed = True

        async def wait_closed(self):
            pass

    # 1. Requesting blocked domain evil.example -> HTTP 403
    reader = asyncio.StreamReader()
    reader.feed_data(b"GET / HTTP/1.1\r\nHost: evil.example\r\n\r\n")
    reader.feed_eof()
    writer = MockWriter()

    await handle_client_inner(reader, writer)
    assert b"403 Forbidden" in writer.data
    assert b"Blocked by policy" in writer.data

    # Clean up policy state
    set_policy(None)
