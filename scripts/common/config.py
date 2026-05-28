"""Optional config helpers.

The pipeline still accepts CLI args and env vars. YAML config is used only when
PyYAML is available, so Spark jobs can run in minimal environments.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "app_config.yaml"


def load_yaml(path=DEFAULT_CONFIG_PATH):
    try:
        import yaml
    except ImportError:
        return load_simple_yaml(path)

    path = Path(path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def parse_scalar(value):
    value = value.strip()
    if value in {"null", "None", ""}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    return value


def load_simple_yaml(path=DEFAULT_CONFIG_PATH):
    """Parse the simple section/key/list YAML used by app_config.yaml."""
    path = Path(path)
    if not path.exists():
        return {}

    config = {}
    current_section = None
    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue

            if not line.startswith(" ") and line.endswith(":"):
                current_section = line[:-1]
                config[current_section] = {}
                continue

            if current_section is None:
                continue

            stripped = line.strip()
            if stripped.startswith("- "):
                if not isinstance(config[current_section], list):
                    config[current_section] = []
                config[current_section].append(parse_scalar(stripped[2:]))
                continue

            if ":" in stripped:
                key, value = stripped.split(":", 1)
                config[current_section][key.strip()] = parse_scalar(value)

    return config


def get_nested(config, *keys, default=None):
    value = config
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def project_path(value):
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str(PROJECT_ROOT / path)
