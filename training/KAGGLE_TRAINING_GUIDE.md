# Kaggle Notebook Training Guide

Use Kaggle only for heavier/manual model training. The free Koyeb backend should not train models at runtime.

## Steps

1. Create a new Kaggle Notebook.
2. Enable Internet in notebook settings.
3. Upload this GitHub repo or clone it:

```bash
!git clone https://github.com/YOUR_USERNAME/ai_stock_analyser.git
%cd ai_stock_analyser
```

4. Install dependencies:

```bash
!pip install -r backend/requirements.txt
```

5. Train the model pack:

```bash
!python backend/scripts/train_model_pack.py --symbols "RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK,SBIN,ITC,TATAMOTORS" --period 5y --max-mb 95 --skip-db-prune
```

6. Download these files and commit them to GitHub:

```text
backend/models/model_pack.joblib
backend/models/model_manifest.json
```

The backend will automatically use the model pack after redeploy.
