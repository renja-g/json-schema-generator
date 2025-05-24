import orjson
import sys
import argparse
from typing import Any, Dict, List, Union, Set

def get_json_type(value: Any) -> str:
    """Convert Python type to JSON Schema type."""
    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "number"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif value is None:
        return "null"
    else:
        print(f"Unknown type: {type(value)}")
        return "unknown"

def normalize_type(schema_type: Union[str, List[str]]) -> Set[str]:
    """Normalize schema type to a set of types."""
    if isinstance(schema_type, str):
        return {schema_type}
    elif isinstance(schema_type, list):
        return set(schema_type)
    else:
        return set()

def merge_types(existing_types: Set[str], new_type: str) -> Union[str, List[str]]:
    """Merge existing schema types with a new type."""
    all_types = existing_types | {new_type}
    if len(all_types) == 1:
        return list(all_types)[0]
    else:
        # Sort types for deterministic output
        type_order = ["null", "boolean", "number", "string", "array", "object"]
        sorted_types = sorted(list(all_types), key=lambda x: type_order.index(x) if x in type_order else 999)
        return sorted_types

def analyze_array_items(items: List[Any], existing_schema: Dict[str, Any] = None) -> Dict[str, Any]:
    """Analyze array items to determine schema structure."""
    if not items:
        return existing_schema or {"type": "array", "items": {}}
    
    # Check if all items are the same type
    types = [get_json_type(item) for item in items]
    unique_types = list(set(types))
    
    if len(unique_types) == 1:
        # Homogeneous array
        item_type = unique_types[0]
        if item_type == "object":
            # All objects - merge their schemas
            merged_schema = generate_object_schema(items[0])
            for item in items[1:]:
                item_schema = generate_object_schema(item)
                merged_schema = merge_object_schemas(merged_schema, item_schema)
            
            # If existing schema exists, merge with it
            if existing_schema and "items" in existing_schema:
                if isinstance(existing_schema["items"], dict) and existing_schema["items"].get("type") == "object":
                    merged_schema = merge_object_schemas(existing_schema["items"], merged_schema)
            
            return {"type": "array", "items": merged_schema}
        else:
            # Handle existing schema
            if existing_schema and "items" in existing_schema:
                if isinstance(existing_schema["items"], dict):
                    existing_types = normalize_type(existing_schema["items"].get("type", ""))
                    new_type = merge_types(existing_types, item_type)
                    return {"type": "array", "items": {"type": new_type}}
            
            return {"type": "array", "items": {"type": item_type}}
    else:
        # Heterogeneous array - use tuple validation
        item_schemas = []
        for item in items:
            if isinstance(item, dict):
                item_schemas.append(generate_object_schema(item))
            else:
                item_schemas.append({"type": get_json_type(item)})
        
        # If existing schema has tuple validation, try to merge
        if existing_schema and "items" in existing_schema and isinstance(existing_schema["items"], list):
            # Extend existing tuple schema
            existing_items = existing_schema["items"][:]
            for i, new_item in enumerate(item_schemas):
                if i < len(existing_items):
                    # Merge with existing item schema
                    if existing_items[i].get("type") == "object" and new_item.get("type") == "object":
                        existing_items[i] = merge_object_schemas(existing_items[i], new_item)
                    elif existing_items[i].get("type") != new_item.get("type"):
                        # Different types - make it more flexible
                        existing_types = normalize_type(existing_items[i].get("type", ""))
                        new_type = merge_types(existing_types, new_item.get("type", ""))
                        existing_items[i] = {"type": new_type}
                else:
                    # Add new item
                    existing_items.append(new_item)
            
            return {
                "type": "array",
                "items": existing_items,
                "additionalItems": existing_schema.get("additionalItems", False)
            }
        
        return {
            "type": "array",
            "items": item_schemas,
            "additionalItems": False
        }

def merge_array_schemas(schema1: Dict[str, Any], schema2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two array schemas."""
    merged = {"type": "array"}
    
    items1 = schema1.get("items", {})
    items2 = schema2.get("items", {})
    
    # Handle tuple validation (items as list)
    if isinstance(items1, list) and isinstance(items2, list):
        # Merge tuple schemas
        max_len = max(len(items1), len(items2))
        merged_items = []
        
        for i in range(max_len):
            item1 = items1[i] if i < len(items1) else None
            item2 = items2[i] if i < len(items2) else None
            
            if item1 and item2:
                if item1.get("type") == "object" and item2.get("type") == "object":
                    merged_items.append(merge_object_schemas(item1, item2))
                elif item1.get("type") == item2.get("type"):
                    merged_items.append(item1)
                else:
                    # Different types - create union
                    type1 = normalize_type(item1.get("type", ""))
                    type2 = normalize_type(item2.get("type", ""))
                    merged_type = merge_types(type1, list(type2)[0] if type2 else "")
                    merged_items.append({"type": merged_type})
            elif item1:
                merged_items.append(item1)
            else:
                merged_items.append(item2)
        
        merged["items"] = merged_items
        merged["additionalItems"] = schema1.get("additionalItems", schema2.get("additionalItems", False))
        
    # Handle single item type (items as object)
    elif isinstance(items1, dict) and isinstance(items2, dict):
        if items1.get("type") == "object" and items2.get("type") == "object":
            merged["items"] = merge_object_schemas(items1, items2)
        elif items1.get("type") == items2.get("type"):
            merged["items"] = items1
        else:
            # Different types - create union
            type1 = normalize_type(items1.get("type", ""))
            type2 = normalize_type(items2.get("type", ""))
            merged_type = merge_types(type1, list(type2)[0] if type2 else "")
            merged["items"] = {"type": merged_type}
    
    # Handle mixed cases
    elif isinstance(items1, list):
        merged["items"] = items1
        merged["additionalItems"] = schema1.get("additionalItems", False)
    elif isinstance(items2, list):
        merged["items"] = items2  
        merged["additionalItems"] = schema2.get("additionalItems", False)
    elif items1:
        merged["items"] = items1
    elif items2:
        merged["items"] = items2
    
    return merged
def merge_object_schemas(schema1: Dict[str, Any], schema2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two object schemas, combining properties and making required fields optional if not in both."""
    merged = {
        "type": "object", 
        "properties": {},
        "required": []
    }
    
    # Get all properties in sorted order for deterministic output
    all_props = sorted(set(schema1.get("properties", {}).keys()) | set(schema2.get("properties", {}).keys()))
    
    for prop in all_props:
        prop1 = schema1.get("properties", {}).get(prop)
        prop2 = schema2.get("properties", {}).get(prop)
        
        if prop1 and prop2:
            # Both schemas have this property - merge them
            if prop1.get("type") == "object" and prop2.get("type") == "object":
                merged["properties"][prop] = merge_object_schemas(prop1, prop2)
            elif prop1.get("type") == "array" and prop2.get("type") == "array":
                merged["properties"][prop] = merge_array_schemas(prop1, prop2)
            elif prop1.get("type") == prop2.get("type"):
                merged["properties"][prop] = prop1  # Same type, keep existing
            else:
                # Different types - make it flexible
                type1 = normalize_type(prop1.get("type", ""))
                type2 = normalize_type(prop2.get("type", ""))
                merged_type = merge_types(type1, list(type2)[0] if type2 else "")
                merged["properties"][prop] = {"type": merged_type}
        elif prop1:
            merged["properties"][prop] = prop1
        else:
            merged["properties"][prop] = prop2
    
    # For required fields: only include fields that are required in BOTH schemas
    # This ensures the new schema validates data that fits either the old or new structure
    req1 = set(schema1.get("required", []))
    req2 = set(schema2.get("required", []))
    merged["required"] = sorted(list(req1 & req2))
    
    return merged

def generate_object_schema(obj: Dict[str, Any], existing_schema: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate schema for a JSON object."""
    schema = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    # Start with existing schema if provided
    if existing_schema and existing_schema.get("type") == "object":
        schema["properties"] = existing_schema.get("properties", {}).copy()
        schema["required"] = existing_schema.get("required", [])[:]
    
    # Process object keys in sorted order for deterministic output
    for key in sorted(obj.keys()):
        value = obj[key]
        existing_prop = schema["properties"].get(key)
        
        if isinstance(value, dict):
            schema["properties"][key] = generate_object_schema(value, existing_prop)
        elif isinstance(value, list):
            schema["properties"][key] = analyze_array_items(value, existing_prop)
        else:
            new_type = get_json_type(value)
            if existing_prop:
                existing_types = normalize_type(existing_prop.get("type", ""))
                merged_type = merge_types(existing_types, new_type)
                schema["properties"][key] = {"type": merged_type}
            else:
                schema["properties"][key] = {"type": new_type}
        
        # Add to required fields if not already there
        if key not in schema["required"]:
            schema["required"].append(key)
    
    schema["required"].sort()
    return schema

def extend_schema(existing_schema: Dict[str, Any], new_data: Any) -> Dict[str, Any]:
    """Create a new schema that accommodates both existing schema and new data."""
    # Create a deep copy to avoid modifying the original
    import copy
    base_schema = copy.deepcopy(existing_schema)
    
    # Generate schema for new data
    new_data_schema = generate_schema(new_data)
    
    # Merge the schemas
    if base_schema.get("type") == "object" and new_data_schema.get("type") == "object":
        merged = merge_object_schemas(base_schema, new_data_schema)
        # Preserve metadata from base schema
        merged["$schema"] = base_schema.get("$schema", "http://json-schema.org/draft-07/schema#")
        merged["title"] = base_schema.get("title", "Extended schema")
        return merged
    elif base_schema.get("type") == "array" and new_data_schema.get("type") == "array":
        # Merge array schemas
        merged = merge_array_schemas(base_schema, new_data_schema)
        merged["$schema"] = base_schema.get("$schema", "http://json-schema.org/draft-07/schema#")
        merged["title"] = base_schema.get("title", "Extended schema")
        return merged
    else:
        # Type mismatch - create a union or use new schema
        return new_data_schema

def generate_schema(data: Any) -> Dict[str, Any]:
    """Generate JSON Schema from JSON data."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Generated schema for Root"
    }
    
    if isinstance(data, dict):
        object_schema = generate_object_schema(data)
        schema.update(object_schema)
    elif isinstance(data, list):
        array_schema = analyze_array_items(data)
        schema.update(array_schema)
    else:
        schema["type"] = get_json_type(data)
    
    return schema

def main():
    parser = argparse.ArgumentParser(description="Generate or extend JSON Schema from JSON data")
    parser.add_argument("input_file", help="Input JSON file")
    parser.add_argument("--base-schema", "-b", help="Existing JSON schema file to extend")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    try:
        # Read JSON data file
        with open(args.input_file, 'rb') as f:
            data = orjson.loads(f.read())
        
        # Read existing schema if provided
        existing_schema = None
        if args.base_schema:
            with open(args.base_schema, 'rb') as f:
                existing_schema = orjson.loads(f.read())
        
        # Generate or extend schema
        if existing_schema:
            print(f"Extending existing schema with new data...", file=sys.stderr)
            schema = extend_schema(existing_schema, data)
        else:
            schema = generate_schema(data)
        
        # Output schema with sorted keys for deterministic output
        output = orjson.dumps(schema, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        
        if args.output:
            with open(args.output, 'wb') as f:
                f.write(output)
            print(f"Schema written to {args.output}")
        else:
            print(output.decode('utf-8'))
        
    except FileNotFoundError as e:
        print(f"Error: File not found: {e}")
        sys.exit(1)
    except orjson.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()