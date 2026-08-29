from __future__ import annotations

import os

from auditor_api import create_auditor_blueprint
from import_api import create_import_blueprint
from operator_ui import create_operator_blueprint
from outcome_api import create_outcome_blueprint
from readiness import create_readiness_blueprint
from repository import RoyaltyRepository
from web_app import create_app


def create_full_app(api_keys=None, repository: RoyaltyRepository | None = None):
    repo = repository or RoyaltyRepository.file(os.getenv("ROYALTYRECOVER_DB_PATH", "royaltyrecover.db"))
    app = create_app(api_keys=api_keys, repository=repo)
    app.register_blueprint(create_operator_blueprint(repo))
    app.register_blueprint(create_auditor_blueprint(repo))
    app.register_blueprint(create_outcome_blueprint(repo))
    app.register_blueprint(create_readiness_blueprint(repo))
    app.register_blueprint(create_import_blueprint(repo))
    return app


app = create_full_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), debug=False)
