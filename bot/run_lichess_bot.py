#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from urllib.parse import urljoin


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    bot_dir = root / "bot" / "lichess-bot"
    config = root / "bot" / "config.yml"

    # The local config file is the source of truth. This avoids stale shell or
    # Windows user environment values overriding the token unexpectedly.
    os.environ.pop("LICHESS_BOT_TOKEN", None)

    sys.path.insert(0, str(bot_dir))
    sys.argv = ["lichess-bot.py", "--config", str(config)]

    from lib import lichess

    original_api_post = lichess.Lichess.api_post

    def api_post_with_slower_token_test(self, endpoint_name, *template_args, **kwargs):
        if endpoint_name != "token_test":
            return original_api_post(self, endpoint_name, *template_args, **kwargs)

        path_template = self.get_path_template(endpoint_name)
        url = urljoin(self.baseUrl, path_template.format(*template_args))
        response = self.session.post(
            url,
            data=kwargs.get("data"),
            headers=kwargs.get("headers"),
            params=kwargs.get("params"),
            json=kwargs.get("payload"),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    lichess.Lichess.api_post = api_post_with_slower_token_test

    from lib.lichess_bot import start_program

    start_program()


if __name__ == "__main__":
    main()
