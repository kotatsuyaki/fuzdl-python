# fuzdl

CLI tool to download manga from Comic FUZ web version.

## External Dependencies

- `geckodriver` (i.e. Firefox webdriver)

## Usage

### Run with Poetry

```sh
export EMAIL="..."
export PASSWORD="..."
SERIES_URL="https://..." poetry run fuzdl
```

### Run with Nix

```sh
export EMAIL="..."
export PASSWORD="..."
SERIES_URL="https://..." nix run .#
```
