import re
import os
import requests
import pandas as pd
import dns.resolver
from tqdm import tqdm
import time
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

hosting_providers = {
    "BigCommerce": "bigcommerce",
    "Elementor": "elementor",
    "GoDaddy": "godaddy",
    "Hostinger": "hostinger",
    "Jimdo": "jimdo",
    "Shopify": "shopify",
    "Squarespace": "squarespace",
    "Webflow": "webflow",
    "Weebly": "weebly",
    "Wix": "wixstatic",
    "WooCommerce": "woocommerce",
    "WordPress.org": ["wp-content", "wp-", "wp-plugins", "wp-json", "wp-block", "wp--preset", "wp-includes"],
    "WordPress.com": "wp.com"
}

name_server_providers = {
    "A2 Hosting": ["a2hosting.com"],
    "AWS": ["awsdns"],
    "Bluehost": ["bluehost.com"],
    "Cloudflare": ["cloudflare.com"],
    "DigitalOcean": ["digitalocean.com"],
    "GoDaddy": ["domaincontrol.com"],
    "Google Domains": ["google.com", "googledomains.com"],
    "HostGator": ["hostgator.com"],
    "Hostinger": ["hostinger"],
    "Namecheap": ["namecheapdns.com", "dns-parking.com", "registrar-servers.com"],
    "SiteGround": ["siteground"],
    "WP Engine": ["wpcdns.com"],
    "WordPress.com": ["wordpress.com"],
    "Wix": ["wixdns.net"],
    "WPX Hosting": ["wpx.net", "wpxhosting.com"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
}

def get_user_input_method():
    print("Choose input method:")
    print("1. Load from .md file")
    print("2. Enter URLs manually")
    print("3. Load from .csv file")
    choice = input("Enter 1, 2 or 3: ").strip()
    while choice not in ["1", "2", "3"]:
        choice = input("Invalid choice. Please enter 1, 2 or 3: ").strip()
    return choice

def extract_links_with_context(filename):
    links_with_context = []
    markdown_link_pattern = r"\[([^\]]+)\]\((https?://[^\s\)]+)\)"
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            matches = re.findall(markdown_link_pattern, line)
            if matches:
                source_name, source_url = matches[0]
                for anchor_text, link in matches[1:]:
                    links_with_context.append((source_name, source_url, link))
    return links_with_context

def normalize_url(url):
    if not url.startswith("http://") and not url.startswith("https://"):
        return "https://" + url
    return url

def get_manual_links():
    print("\nEnter URLs to check (one per line). Type 'done' when finished:")
    manual_links = []
    while True:
        link = input("URL: ").strip()
        if link.lower() == "done":
            break
        if link:
            normalized = normalize_url(link)
            manual_links.append(("Manual Entry", "N/A", normalized))
        else:
            print("❌ Invalid URL.")
    return manual_links

def get_links_from_csv():
    file_path = input("\nEnter the path to your CSV file: ").strip()
    column_name = input("Enter the column name containing the URLs (default: 'URL'): ").strip()
    if column_name == "":
        column_name = "URL"
    try:
        df = pd.read_csv(file_path)
        if column_name not in df.columns:
            print(f"❌ Column '{column_name}' not found in CSV.")
            return []
        return [("CSV Entry", "N/A", normalize_url(url)) for url in df[column_name].dropna() if isinstance(url, str)]
    except FileNotFoundError:
        print("❌ File not found.")
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
    return []

def identify_host(html):
    soup = BeautifulSoup(html, "html.parser")
    head_tag = soup.head
    if not head_tag:
        return "Other"
    head_text = " ".join(head_tag.stripped_strings).lower()
    meta_content = " ".join([meta.get("content", "").lower() for meta in head_tag.find_all("meta")])
    script_srcs = " ".join([script.get("src", "").lower() for script in head_tag.find_all("script") if script.get("src")])
    link_hrefs = " ".join([link.get("href", "").lower() for link in head_tag.find_all("link") if link.get("href")])
    title_content = head_tag.title.string.lower() if head_tag.title else ""
    combined_text = f"{head_text} {meta_content} {script_srcs} {link_hrefs} {title_content}"
    for provider, keywords in hosting_providers.items():
        if isinstance(keywords, list):
            if any(keyword in combined_text for keyword in keywords):
                return provider
        elif keywords in combined_text:
            return provider
    return "Other"

def get_name_server_provider(domain):
    try:
        answers = dns.resolver.resolve(domain, 'NS')
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        # Try base domain if initial lookup fails
        parts = domain.split('.')
        if len(parts) > 2:
            base_domain = '.'.join(parts[-2:])
            try:
                answers = dns.resolver.resolve(base_domain, 'NS')
            except Exception:
                return "DNS Lookup Failed"
        else:
            return "DNS Lookup Failed"

    ns_servers = [str(rdata).strip('.') for rdata in answers]
    for provider, keywords in name_server_providers.items():
        if any(any(keyword in ns for keyword in keywords) for ns in ns_servers):
            return provider
    return ", ".join(ns_servers)

def check_hosting(links_with_context):
    results = []
    print("\nChecking website hosting & name servers...")
    for source_name, source_url, link in tqdm(links_with_context, desc="Progress", unit="site"):
        host = "Other"
        ns_provider = "Unknown"
        try:
            response = requests.get(link, headers=HEADERS, timeout=10, verify=False)
            response.raise_for_status()
            host = identify_host(response.text)
            domain = re.sub(r"https?://(www\\.)?", "", link).split("/")[0]
            ns_provider = get_name_server_provider(domain)
        except requests.exceptions.Timeout:
            host = "Timeout (Increase timeout)"
            print(f"❌ Timeout: {link}")
        except requests.exceptions.SSLError:
            host = "SSL Error (Invalid Cert)"
            print(f"❌ SSL Error: {link}")
        except requests.exceptions.HTTPError as e:
            host = f"[ERROR] HTTP Error {response.status_code}"
            print(f"❌ HTTP Error {response.status_code}: {link}")
        except requests.exceptions.ConnectionError:
            host = "[ERROR] Connection Error"
            print(f"❌ Connection Error: {link}")
        except requests.exceptions.RequestException:
            host = "[ERROR] Request Failed"
            print(f"❌ Request Failed: {link}")
        results.append((source_name, source_url, link, host, ns_provider))
        time.sleep(1)
    return results

def save_to_excel(data, input_type, output_filename="host_checker_results.xlsx"):
    if input_type == "md":
        df = pd.DataFrame(data, columns=["Name", "Profile", "URL", "Host", "NS Provider"])
    else:
        df = pd.DataFrame([(url, host, ns) for _, _, url, host, ns in data],
                          columns=["URL", "Host", "NS Provider"])
    df.to_excel(output_filename, index=False)
    print(f"\nResults saved to {output_filename}")

if __name__ == "__main__":
    choice = get_user_input_method()
    if choice == "1":
        input_type = "md"
        filename = input("\nEnter the path to your Markdown (.md) file: ").strip()
        links_with_context = extract_links_with_context(filename)
    elif choice == "2":
        input_type = "manual"
        links_with_context = get_manual_links()
    elif choice == "3":
        input_type = "csv"
        links_with_context = get_links_from_csv()

    if links_with_context:
        hosting_results = check_hosting(links_with_context)
        save_to_excel(hosting_results, input_type)
    else:
        print("No valid links to check.")
