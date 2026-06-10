import re
import json

# 1. PASTE YOUR COPIED "NODE.JS FETCH" BLOCK EXACTLY BETWEEN THE TRIPLE QUOTES BELOW:
NODE_FETCH_INPUT = """
fetch("https://music.youtube.com/youtubei/v1/browse?ctoken=...", {
  "headers": {
    "accept": "*/*",
    "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "authorization": "SAPISIDHASH 1781081177_444d0548028ed4931ece1e77ecbcdaaeed7b40ac_u",
    "content-encoding": "gzip",
    "content-type": "application/json",
    "x-goog-authuser": "0",
    "x-origin": "https://music.youtube.com",
    "cookie": "__Secure-BUCKET=CM8C; LOGIN_INFO=..."
  },
  "method": "POST"
});
"""

def extract_and_normalize_headers(raw_fetch_text, output_filepath="browser.json"):
    """Parses a raw JavaScript Node.js fetch code snippet string, extracts

    the core required YouTube Music credentials, and writes a clean JSON file.
    """
    # Explicit whitelist defining canonical canonicalized target output casing
    target_fields = {
        "accept": "Accept",
        "authorization": "Authorization",
        "content-type": "Content-Type",
        "x-goog-authuser": "X-Goog-AuthUser",
        "x-origin": "X-Origin",
        "cookie": "Cookie"
    }
    
    browser_json_payload = {}
    
    # Matches both double or single quoted key-value pairs (e.g., "key": "value")
    pair_pattern = re.compile(r'["\']([^"\']+)["\']\s*:\s*["\']([^"\']+)["\']')
    
    # Sweep through the string log blocks to discover targets
    for match in pair_pattern.finditer(raw_fetch_text):
        key, val = match.groups()
        key_lower = key.lower()
        
        if key_lower in target_fields:
            canonical_key = target_fields[key_lower]
            browser_json_payload[canonical_key] = val

    # Verify that the two absolute required verification signatures were found
    if "Cookie" not in browser_json_payload or "Authorization" not in browser_json_payload:
        print("⚠️ Warning: Critical authentication credentials (Cookie/Authorization) were missing from the code block!")
    
    # Write to a clean valid JSON file structure
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(browser_json_payload, f, indent=4)
        
    print(f"✅ Success! Generated '{output_filepath}' with {len(browser_json_payload)} clean, isolated fields.")
    return browser_json_payload

if __name__ == "__main__":
    # Run the processing method automatically
    extract_and_normalize_headers(NODE_FETCH_INPUT)