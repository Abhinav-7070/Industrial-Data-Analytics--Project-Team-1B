from pathlib import Path
import config as cfg
from generator import generate_all

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def main():
    DATA_DIR.mkdir(exist_ok=True)
    df = generate_all()
    out = DATA_DIR / cfg.OUTPUT_FILENAME
    df.to_csv(out, index=False)
    print(f"Saved {len(df):,} rows x {df.shape[1]} columns -> {out}")
    print(df.head())


if __name__ == "__main__":
    main()
    
