# v8 Forecast Model

The v8 forecaster is a phase-aware model designed to predict Roblox Up-and-Coming chart ranks.

## Branch Logic
The model switches behavior based on `task.json` found in the input directory:
- **DEV Branch**: Used for practice window inputs (timestamps before 2026-11-10). It returns a baked-in frequency table of the practice-window reads.
- **FINAL Branch**: Used for the final scored window. It employs a forecaster model based on previous v6 machinery, enhanced with:
    - A stronger occupancy prior.
    - An occupancy-momentum term.
    - A new-entrant boost for recent games.

## Constants (FINAL Branch)
- **GAMMA**: 0.12 (Occupancy prior weight)
- **BETA**: 0.06 (Momentum strength)
- **MOM_CLIP**: 0.04 (Momentum clipping)
- **ETA**: 0.01 (New-entrant boost)

## Usage
Ensure `MAKEFUN_INPUT_DIR` and `MAKEFUN_OUTPUT_DIR` environment variables are set correctly, then run:
```bash
python3 repo/main.py
```
The script will automatically detect the branch and generate `forecast.json` in the output directory.
