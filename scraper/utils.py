def load_store_ids_from_file(filepath="store_ids.txt"):
    ids = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))
    except FileNotFoundError:
        print(f"⚠️ Store IDs file not found: {filepath}")
    return ids
