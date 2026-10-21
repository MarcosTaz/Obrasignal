from pathlib import Path

from production_ci_safety import DEFAULT_WORKFLOW, classify_workflow, load_and_classify


def test_current_canonical_authenticated_e2e_is_truthfully_unsafe():
    result = load_and_classify(DEFAULT_WORKFLOW)
    assert result.classification == 'UNSAFE_AUTOMATIC_PRODUCTION_WRITE'
    assert set(result.automatic_triggers) == {'push', 'schedule'}
    assert result.production_target is True
    assert 'POST' in result.production_writes


def test_automatic_production_read_only_is_ready_for_this_safety_gate():
    text = '''
name: Auth E2E
on:
  push:
    branches: [main]
  schedule:
    - cron: "0 2 * * *"
env:
  API_URL: https://obrasignal.onrender.com/api/v1
jobs:
  probe:
    steps:
      - run: curl "$API_URL/profile"
'''
    result = classify_workflow(text)
    assert result.classification == 'READ_ONLY_AUTOMATIC_PRODUCTION'
    assert result.read_only_automatic_production is True
    assert result.production_writes == ()


def test_restore_logic_does_not_neutralize_a_production_write():
    text = '''
on:
  push:
    branches: [main]
env:
  API_URL: https://obrasignal.onrender.com/api/v1
jobs:
  probe:
    steps:
      - run: |
          restore() { echo restore; }
          trap restore EXIT
          curl -X POST "$API_URL/profile" --data '{}'
'''
    result = classify_workflow(text)
    assert result.classification == 'UNSAFE_AUTOMATIC_PRODUCTION_WRITE'
    assert result.production_writes == ('POST',)


def test_manual_production_write_requires_separate_authorization():
    text = '''
on:
  workflow_dispatch:
env:
  API_URL: https://obrasignal.onrender.com/api/v1
jobs:
  probe:
    steps:
      - run: curl --request DELETE "$API_URL/profile"
'''
    result = classify_workflow(text)
    assert result.classification == 'MANUAL_PRODUCTION_WRITE_REQUIRES_AUTHORIZATION'
    assert result.read_only_automatic_production is False


def test_automatic_unknown_target_fails_closed_instead_of_claiming_safe():
    text = '''
on:
  schedule:
    - cron: "0 2 * * *"
env:
  API_URL: ${{ secrets.API_URL }}
jobs:
  probe:
    steps:
      - run: curl "$API_URL/profile"
'''
    result = classify_workflow(text)
    assert result.classification == 'UNKNOWN_AUTOMATIC_TARGET'
    assert result.read_only_automatic_production is False


def test_default_workflow_path_is_repository_workflow():
    assert Path(DEFAULT_WORKFLOW).as_posix().endswith('.github/workflows/authenticated-e2e.yml')
