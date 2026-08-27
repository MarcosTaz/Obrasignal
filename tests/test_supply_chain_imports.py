import supply_chain_imports


def test_production_python_external_imports_are_declared_directly():
    report = supply_chain_imports.inventory()
    leaks = [item for item in report["imports"] if item["status"] == "TRANSITIVE_LEAK_OR_UNDECLARED"]
    assert leaks == [], f"undeclared/transitive production imports: {leaks}"


def test_python_dependency_authority_is_requirements_not_import_success():
    declared = supply_chain_imports.declared_requirements()
    assert declared == {
        "Flask": "Flask>=3.1,<4",
        "requests": "requests>=2.32,<3",
        "gunicorn": "gunicorn>=23,<24",
        "PyJWT[crypto]": "PyJWT[crypto]>=2.10,<3",
    }
