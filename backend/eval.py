"""eval harness: run extractor over labeled corpus, print accuracy."""
import json
from pathlib import Path
from extractor import extract_dna
from guard import detect_injection

DATA_DIR = Path(__file__).parent / "data"
CORPUS = DATA_DIR / "corpus.json"

def main():
    if not CORPUS.exists():
        print("No corpus.json found. Create one with [{\"text\": \"...\", \"is_scam\": bool}]")
        return
    corpus = json.loads(CORPUS.read_text())
    correct = 0
    total = len(corpus)
    tp = fp = tn = fn = 0
    for item in corpus:
        text = item["text"]
        label = item.get("is_scam", False)
        result = extract_dna(text)
        predicted = result.get("is_scam", False)
        if predicted == label:
            correct += 1
        if predicted and label:
            tp += 1
        elif predicted and not label:
            fp += 1
        elif not predicted and not label:
            tn += 1
        else:
            fn += 1
    acc = correct / total * 100 if total else 0
    prec = tp / (tp + fp) * 100 if (tp + fp) else 0
    rec = tp / (tp + fn) * 100 if (tp + fn) else 0
    print(f"Extractor accuracy: {acc:.1f}% ({correct}/{total})")
    print(f"  Precision: {prec:.1f}%  Recall: {rec:.1f}%")
    print(f"  TP={tp} FP={fp} TN={tn} FN={fn}")

    inj_correct = 0
    for item in corpus:
        if "has_injection" in item:
            result = detect_injection(item["text"])
            predicted = result.get("detected", False)
            if predicted == item["has_injection"]:
                inj_correct += 1
    inj_total = sum(1 for i in corpus if "has_injection" in i)
    if inj_total:
        print(f"\nInjection detector accuracy: {inj_correct/inj_total*100:.1f}% ({inj_correct}/{inj_total})")

if __name__ == "__main__":
    main()