#!/usr/bin/env bash
# Download raw DepMap 23Q4 Public matrices into .depmap_cache/.
#
# The current DepMap portal (25Q2+) gates downloads behind a Cloudflare
# challenge, so we pull the 23Q4 Public release from Figshare, whose
# `ndownloader` URLs are ungated and stable. Biology is release-stable; 23Q4 is
# fine for the demo. To refresh to a newer release, download the same five files
# manually from https://depmap.org/portal/data_page/ into this folder.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .depmap_cache && cd .depmap_cache

dl() { echo "fetching $1 ..."; curl -fSL "$2" -o "$1"; }

dl Model.csv                          https://ndownloader.figshare.com/files/43746708
dl AchillesCommonEssentialControls.csv https://ndownloader.figshare.com/files/43346361
dl CRISPRInferredCommonEssentials.csv https://ndownloader.figshare.com/files/43346706
dl CRISPRGeneEffect.csv               https://ndownloader.figshare.com/files/43346616   # ~382 MB
dl OmicsCNGene.csv                    https://ndownloader.figshare.com/files/43346913   # ~763 MB

echo "done. now run:  python build_subset.py"
