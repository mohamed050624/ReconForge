"""Markdown report and AI handoff builders for ReconForge V1."""

from __future__ import annotations


def md_list(values: list[str], limit: int = 30) -> str:
    """Render values as Markdown bullet list."""
    if not values:
        return "_No data._"

    rendered = "\n".join(f"- `{value}`" for value in values[:limit])
    remaining = len(values) - limit

    if remaining > 0:
        rendered += f"\n- _...and {remaining} more._"

    return rendered


def build_program_report(context: dict) -> str:
    """Build Markdown program report."""
    summary = context["summary"]
    api = context["api_attack_surface"]
    assets = context["assets"]
    urls = context["urls"]

    lines = [
        f"# ReconForge One Program Report: {context['program']}",
        "",
        f"Generated at: `{context['generated_at']}`",
        "",
        "## Safety Boundaries",
        "",
        "- Authorized scope required.",
        "- Passive and non-destructive reconnaissance only.",
        "- No exploitation automation.",
        "- No DoS, credential attacks, social engineering, or destructive testing.",
        "",
        "## Summary",
        "",
        f"- Root targets: **{summary['root_targets']}**",
        f"- Subdomains discovered: **{summary['subdomains_discovered']}**",
        f"- Resolved subdomains: **{summary['subdomains_resolved']}**",
        f"- Live hosts: **{summary['live_hosts']}**",
        f"- URLs collected: **{summary['urls']}**",
        f"- API hosts: **{summary['api_hosts']}**",
        f"- API endpoints: **{summary['api_endpoints']}**",
        f"- Parameters: **{summary['parameters']}**",
        f"- GraphQL candidates: **{summary['graphql_candidates']}**",
        f"- Swagger/OpenAPI candidates: **{summary['swagger_openapi_candidates']}**",
        f"- Auth endpoints: **{summary['auth_endpoints']}**",
        f"- Upload endpoints: **{summary['upload_endpoints']}**",
        f"- JS files: **{summary['js_files']}**",
        "",
        "## High Signal Assets",
        "",
        md_list(assets["high_signal_assets"], 50),
        "",
        "## Live Hosts Sample",
        "",
        md_list(assets["live_hosts_sample"], 50),
        "",
        "## API Attack Surface",
        "",
        "### API Hosts",
        "",
        md_list(api["api_hosts"], 50),
        "",
        "### API Endpoints Sample",
        "",
        md_list(api["api_endpoints_sample"], 80),
        "",
        "### GraphQL Candidates",
        "",
        md_list(api["graphql_candidates"], 50),
        "",
        "### Swagger / OpenAPI Candidates",
        "",
        md_list(api["swagger_openapi_candidates"], 50),
        "",
        "### Auth Endpoints",
        "",
        md_list(api["auth_endpoints_sample"], 50),
        "",
        "### Upload Endpoints",
        "",
        md_list(api["upload_endpoints_sample"], 50),
        "",
        "### Parameters",
        "",
        md_list(api["parameters"], 80),
        "",
        "## Interesting URLs",
        "",
        md_list(urls["interesting_urls_sample"], 100),
        "",
        "## Important Files",
        "",
    ]

    for name, path in context["important_files"].items():
        lines.append(f"- **{name}:** `{path}`")

    lines.extend(
        [
            "",
            "## Manual Review Focus",
            "",
            "- Confirm every reviewed asset is inside official scope.",
            "- Prioritize API authorization, IDOR/BOLA, session handling, exposed docs, and upload logic.",
            "- Review admin/dev/staging-looking hosts manually.",
            "- Review archived URLs for forgotten endpoints.",
            "- Treat unclear assets as needing scope verification.",
            "",
        ]
    )

    return "\n".join(lines)


def build_ai_prompt(program: str) -> str:
    """Build reusable AI prompt."""
    return f"""You are assisting with an authorized Bug Bounty reconnaissance review for {program}.

I will provide:
1. ReconForge One AI handoff
2. Program-level AI context JSON
3. Official policy notes copied from the program page

Important rules:
- Only analyze assets that are clearly in scope.
- Do not suggest testing assets listed as excluded or out of scope.
- Do not suggest denial-of-service testing.
- Do not suggest credential attacks.
- Do not suggest social engineering.
- Do not suggest destructive testing.
- Do not suggest exploitation automation.
- If an asset is unclear, mark it as "Needs scope verification".
- Focus on safe manual testing ideas only.

Task:
Analyze the ReconForge handoff and produce a prioritized manual testing plan.

Return:

1. Scope confirmation
- Clearly in-scope assets
- Assets needing scope verification
- Excluded/out-of-scope assets to avoid

2. Attack surface summary
- Subdomains
- Live hosts
- Technologies
- URLs
- API surface
- Interesting patterns

3. Top priority assets table
Columns:
- Priority
- Asset / URL
- Why it matters
- Suggested safe manual review

4. API review plan
Focus on:
- API authorization
- IDOR/BOLA
- Auth/session logic
- GraphQL authorization
- Swagger/OpenAPI exposure
- Upload/media logic
- Excessive data exposure

5. Interesting endpoints and parameters

6. Likely vulnerability categories for manual review

7. Non-destructive validation plan

8. Missing reconnaissance data

9. Final risk-ranked manual testing order
"""


def build_ai_handoff(context: dict, program_report: str, policy_notes: str) -> str:
    """Build AI handoff Markdown."""
    prompt = build_ai_prompt(context["program"])

    return "\n\n".join(
        [
            f"# ReconForge One AI Handoff: {context['program']}",
            "## Read This First",
            (
                "This handoff was generated from passive, non-destructive "
                "reconnaissance for authorized Bug Bounty / penetration testing review."
            ),
            "## Official Policy Notes Copied by User",
            policy_notes,
            "## Program Recon Report",
            program_report,
            "## AI Prompt",
            prompt,
            "## Full JSON Context",
            (
                "Use `program_ai_context.json` for structured data. "
                "Large full lists are stored in `02_clean/`."
            ),
        ]
    )
