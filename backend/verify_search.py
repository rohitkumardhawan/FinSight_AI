import httpx
import time

def test_queries():
    print("Testing live search queries against FastAPI backend (127.0.0.1:8000)...")
    for q in ['asian', 'tata', 'apple']:
        t0 = time.time()
        url = f"http://127.0.0.1:8000/api/companies/search?q={q}"
        res = httpx.get(url, timeout=25.0)
        dur = round(time.time() - t0, 2)
        print(f"\nQuery [{q}] ({dur}s) -> Status: {res.status_code}, Found: {len(res.json())}")
        for item in res.json()[:3]:
            print(f"   - {item.get('symbol')} | {item.get('name')} | Exchange: {item.get('exchange')} | Currency: {item.get('currency')} | Cached: {item.get('is_cached')}")

if __name__ == "__main__":
    test_queries()
