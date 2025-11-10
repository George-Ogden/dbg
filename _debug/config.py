import configparser
from dataclasses import dataclass
import difflib
import inspect
import os.path
import re
from typing import Any, ClassVar, Literal
import warnings

import platformdirs

from . import defaults as defaults
from .code import validate_style


@dataclass
class DbgConfig:
    color: bool | Literal["auto"]
    sort_unordered_collections: bool
    indent: int
    style: str

    def __init__(self) -> None:
        self._style = defaults.DEFAULT_STYLE
        self.color = "auto"
        self.indent = defaults.DEFAULT_INDENT
        self.sort_unordered_collections = False

    _FILENAME: ClassVar[str] = "dbg.conf"
    _SECTION: ClassVar[str] = "dbg"
    _DEFAULT_VALUE: ClassVar[Any] = object()
    _USER_FILENAME: ClassVar[str] = os.path.join(platformdirs.user_config_dir("debug"), _FILENAME)
    _LOCAL_FILENAME: ClassVar[str] = os.path.join(os.getcwd(), _FILENAME)

    @property  # type: ignore
    def style(self) -> str:
        return self._style

    @style.setter
    def style(self, value: str) -> None:
        try:
            validate_style(value)
        except ValueError as e:
            warnings.warn(str(e))
        else:
            self._style = value

    def use_config(self, filepath: str) -> None:
        filepath = os.path.abspath(filepath)
        config = configparser.ConfigParser()
        try:
            with open(filepath) as f:
                config_string = f.read()
        except OSError as e:
            warnings.warn(f"Unable to load config from '{filepath}'. ({type(e).__name__})")
            return
        try:
            config.read_string(config_string)
        except configparser.MissingSectionHeaderError:
            config_string = f"[{self._SECTION}]\n" + config_string
        try:
            config.read_string(config_string)
        except configparser.Error as e:
            warnings.warn(f"Unable to load config from '{filepath}'. ({type(e).__name__})")
            return
        annotations = inspect.get_annotations(type(self))
        if len(config.sections()) > 1:
            for section_name in config.sections():
                if section_name != self._SECTION:
                    warnings.warn(
                        f"Extra section [{section_name}] found in '{filepath}'. "
                        "Please, use no sections or one section called [dbg]."
                    )
        elif self._SECTION not in config.sections():
            for section_name in config.sections():
                warnings.warn(
                    f"Wrong section [{section_name}] used in '{filepath}'. "
                    "Please, use [dbg] or no sections."
                )
        for section_name in config.sections():
            section = config[section_name]
            for key in section.keys():
                value_type = annotations.get(key, None)
                value: Any
                if value_type is None:
                    warning_msg = f"Unused field '{key}' found in '{filepath}'."
                    suggestions = difflib.get_close_matches(
                        key, possibilities=annotations.keys(), n=1
                    )
                    if suggestions:
                        [suggestion] = suggestions
                        warning_msg += f" Did you mean {suggestion!r}?"
                    warnings.warn(warning_msg)
                    continue
                if value_type is bool:
                    try:
                        value = section.getboolean(key)
                    except ValueError:
                        self.warn_invalid_type(
                            expected="bool", key=key, filepath=filepath, value=section[key]
                        )
                        continue
                elif value_type == bool | Literal["auto"]:
                    try:
                        value = section.getboolean(key)
                    except ValueError:
                        value = self.remove_quotes(section[key], filepath=filepath)
                        if value != "auto":
                            self.warn_invalid_type(
                                expected="bool or 'auto'", key=key, filepath=filepath, value=value
                            )
                            continue
                elif value_type is int:
                    try:
                        value = section.getint(key)
                    except ValueError:
                        self.warn_invalid_type(
                            expected=value_type.__name__,
                            key=key,
                            filepath=filepath,
                            value=section[key],
                        )
                        continue
                else:
                    value = self.remove_quotes(section[key], filepath=filepath)

                setattr(self, key, value)

    @classmethod
    def remove_quotes(cls, value: str, *, filepath: str) -> str:
        match = re.match(r"^('(.*)'|\"(.*)\")$", value)
        if match:
            warnings.warn(
                f"Quotes used around {value} in '{filepath}'. "
                "They will be ignored, but please remove to silence this warning."
            )
            value = (match.group(2) or "") + (match.group(3) or "")
        return value

    @classmethod
    def warn_invalid_type(cls, *, expected: str, key: str, filepath: str, value: str) -> None:
        warnings.warn(
            f"Invalid value {value!r} found in field {key!r} (expected {expected}) in '{filepath}'."
        )


CONFIG = DbgConfig()
if not os.path.exists(CONFIG._USER_FILENAME):
    os.makedirs(os.path.dirname(CONFIG._USER_FILENAME), exist_ok=True)
    try:
        with (
            open(CONFIG._USER_FILENAME, "x") as config_file,
            open(os.path.join(os.path.dirname(__file__), "default.conf")) as default_file,
        ):
            config_file.write(default_file.read())
    except OSError:
        ...

CONFIG.use_config(CONFIG._USER_FILENAME)
if os.path.exists(CONFIG._LOCAL_FILENAME):
    CONFIG.use_config(CONFIG._LOCAL_FILENAME)
