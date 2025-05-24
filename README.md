# JSON Schema Generator

**A command-line tool to generate or extend JSON Schemas based on input JSON data.**

## Features

* **Input JSON**: Automatically detects the structure and infers appropriate JSON Schema types.
* **Schema Extension**: Merge new data into existing schemas.
* **Deterministic Output**: Ensures consistent results by sorting keys and types.

## Usage

```bash
python main.py input.json [--base-schema existing_schema.json] [--output output_schema.json]
```

### Arguments

| Argument             | Description                                               |
| -------------------- | --------------------------------------------------------- |
| `input.json`         | Path to the input JSON file.                              |
| `--base-schema` `-b` | (Optional) Existing schema to extend with the new data.   |
| `--output` `-o`      | (Optional) Output file path. Prints to stdout if omitted. |

### Examples

**Generate schema from JSON data:**

```bash
python main.py example.json
```

**Extend an existing schema:**

```bash
python main.py new_data.json --base-schema existing_schema.json --output merged_schema.json
```
