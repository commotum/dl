# cookiekit TODO

## Status

`cookiekit` is effectively done for the personal-tools scope.

It already covers the main job:

- read cookies from a logged-in browser profile
- optionally filter by domain or Firefox container
- export Netscape `cookies.txt`

Treat this package as maintenance mode, not active expansion.

## Only keep if needed

- [ ] Add `list-profiles`
- [ ] Add `list-containers`
- [ ] Improve error messages for common mistakes: wrong browser name, wrong profile name or path, wrong container name, unsupported Chromium keyring choice, no matching cookie DB found
- [ ] Add a few regression tests if profile selection or Chromium decryption causes real problems

## Root CLI

- [ ] Add a simple root-level wrapper so `cookiekit` can be invoked from the repo root in the same style as the future `requestkit` and `downloadkit` CLIs
