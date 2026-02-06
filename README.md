# Aetos.Products

Product data repository for the Aetos arbitrage automation system.

## Structure

```
Products/
├── Cameras/
│   ├── Canon/          # Individual Canon camera YAML files
│   ├── Nikon/          # Individual Nikon camera YAML files
│   └── Matching/       # Shared matching rules for all cameras
│       ├── filters_reject.yml
│       └── filters_boost.yml
├── VR_Headsets/        # Future: VR products
└── Gaming/             # Future: Gaming products
```

## Camera YAML Structure

Each camera has its own YAML file with the following structure:

```yaml
brand: Canon
model: 600D
full_name: Canon EOS 600D / Rebel T3i
category: DSLR

pricing:
  buy_min: 70      # Minimum price to buy at
  buy_max: 100     # Maximum price to buy at
  sell_target: 150 # Target selling price

# Official model name variations
aliases:
  - 600d
  - eos 600d
  - rebel t3i
  - t3i
  - kiss x5

# Typos, spacing variations for fuzzy matching
fuzzy_patterns:
  - cannon 600d      # common typo
  - canon 600 d      # spacing variation
  - canon d600       # reversed
  - eos600d          # no space

active: true
```

## Shared Matching Files

### filters_reject.yml
Keywords that automatically disqualify a listing (e.g., "broken", "for parts").
Shared across ALL cameras.

### filters_boost.yml
Keywords that increase confidence in a listing (e.g., "mint condition", "with box").
Shared across ALL cameras.

## Usage

### Adding a New Camera

1. Create a new YAML file in the appropriate brand folder:
   ```
   Products/Cameras/Canon/850D.yml
   ```

2. Fill in the camera details using the structure above

3. Run the database update script:
   ```bash
   ./scripts/updateDatabase.sh
   ```

### Editing Products

1. Edit the YAML files directly
2. Commit changes to Git
3. Run `./scripts/updateDatabase.sh` to sync changes to database

### Validation

Run the validation script to check all YAML files are valid:
```bash
python scripts/validate_products.py
```

## Database Sync

The `updateDatabase.sh` script:
- Reads all YAML files
- Validates the data
- Upserts into the database (updates if exists, inserts if new)
- Logs all changes

## Notes

- `category` field is for informational purposes only
- Matching is done using `brand`, `model`, `aliases`, and `fuzzy_patterns`
- Always test new products before activating with `active: true`
- Keep `buy_max < sell_target` to ensure profitability

## Generated Files

This repository was generated using `scripts/setup_products.py`
- Total cameras: 64 (Canon: 35, Nikon: 29)
- All cameras set to `active: true`
- Shared filters created for all camera products
