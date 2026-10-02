from pathlib import Path

from modules.cli import main


def test_cli_end_to_end(tmp_path, capsys):
    (tmp_path / "config.toml").write_text(Path("config.toml").read_text())
    assert main(["--project", str(tmp_path), "init"]) == 0
    assert main(["--project", str(tmp_path), "start", "Linear algebra"]) == 0
    assert main(["--project", str(tmp_path), "resume"]) == 0
    assert main(["--project", str(tmp_path), "validate"]) == 0


def test_cli_validate_fails_on_bad_config_and_corrupt_log(tmp_path, capsys):
    main(["--project", str(tmp_path), "init"])
    main(["--project", str(tmp_path), "start", "topic"])
    (tmp_path / "config.toml").write_text("[mastery]\npass_threshold = 5\n")
    assert main(["--project", str(tmp_path), "validate"]) == 1
    assert "config" in capsys.readouterr().err
