import requests
from bs4 import BeautifulSoup
import re
import time

BASE_URL = "https://min-repo.com/category/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

# All 47 prefectures of Japan
PREFECTURES = [
    "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
    "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
    "新潟県","富山県","石川県","福井県","山梨県","長野県",
    "岐阜県","静岡県","愛知県","三重県",
    "滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
    "鳥取県","島根県","岡山県","広島県","山口県",
    "徳島県","香川県","愛媛県","高知県",
    "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県"
]

def get_store_ids_from_pref(prefecture: str):
    """Fetch all store IDs from a prefecture page"""
    url = f"{BASE_URL}{prefecture}/"
    print(f"Fetching: {url}")
    store_ids = set()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"⚠️ Failed {url} (status {resp.status_code})")
            return store_ids

        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for store links like https://min-repo.com/2564229/
        for link in soup.find_all("a", href=True):
            m = re.match(r"^https?://min-repo\.com/(\d+)/$", link["href"])
            if m:
                store_ids.add(int(m.group(1)))

    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")

    return store_ids

def main():
    all_ids = set()
    for pref in PREFECTURES:
        ids = get_store_ids_from_pref(pref)
        print(f"  → Found {len(ids)} stores in {pref}")
        all_ids.update(ids)
        time.sleep(1)  # polite delay

    print(f"\n✅ Total unique stores found: {len(all_ids)}")

    with open("store_ids.txt", "w", encoding="utf-8") as f:
        for sid in sorted(all_ids):
            f.write(str(sid) + "\n")

    print("📁 Saved all store IDs to store_ids.txt")

if __name__ == "__main__":
    main()
