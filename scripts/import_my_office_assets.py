#!/usr/bin/env python3
"""Import approved V23+4K assets from the reviewed release ZIP; refuse substitutions."""
import hashlib
import os
import sys
import zipfile
from pathlib import Path

RECORDS = {
 "approved_assets/v23_champagne/01-champagne.png":("champagne-v23.png","f9383f0c2de0d78dea287e74c2eded9e50c9dea9383238f2033cd6082a3a8606"),
 "approved_assets/4K_web/01_champanhe_aurora.webp":("champagne-4k.webp","3fe62df824551aa766d83979997ba3dc6fe0cfb904738295426f7f4b7da28382"),
 "approved_assets/4K_web/02_cobre_horizonte.webp":("copper-4k.webp","e828e18aff7d17ad957f342be7978878746eae94f61bbdcf733ec7c298499684"),
 "approved_assets/4K_web/03_azul_cobalto.webp":("cobalt-4k.webp","d43690f0bd09bc1493b582e95f33b47f422b25a05bcf21f4d0cc70a374d2e87e"),
 "approved_assets/4K_web/04_verde_petroleo.webp":("emerald-4k.webp","3e2694fabf7bdf1096f4f617317eded081f6b477f670189d2bb6e4323a638b9a"),
 "approved_assets/4K_web/05_gelo_prata.webp":("ivory-4k.webp","a7301d09499b20634fbc4f31ceea283e31ab7e0b9c3d543fc7cc3b24e7369b90"),
 "approved_assets/4K_web/06_rubi_carbono.webp":("crimson-4k.webp","7acd6443240b80ea7676fd036b18bf26fc6ebb6e7216b172b911190ae2dabe28"),
 "approved_assets/4K_web/07_ametista_nocturna.webp":("violet-4k.webp","17626ad9c9adab2bc1d6f96dc5f7a733d5ef0c8f221659c3ca94b1dc"),
}
def install(archive, directory):
    archive=Path(archive)
    dest=Path(directory)
    if not archive.is_file():
        raise ValueError(f"missing input ZIP: {archive}")
    verified={}
    with zipfile.ZipFile(archive) as z:
        for src,(name,sha) in RECORDS.items():
            if src not in z.namelist():
                raise ValueError(f"missing approved asset: {src}")
            with z.open(src) as stream:
                data=stream.read(12_000_000)
                if stream.read(1):raise ValueError(f"oversize asset: {src}")
            actual=hashlib.sha256(data).hexdigest()
            if actual!=sha:raise ValueError(f"hash mismatch for {src}")
            verified[name]=data
    dest.mkdir(parents=True,exist_ok=True)
    for name,data in verified.items():
        tmp=dest/('.'+name+'.tmp')
        tmp.write_bytes(data)
        os.replace(tmp,dest/name)
    print(f"Verified and installed {len(verified)} original assets in {dest}")
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit("Usage: python scripts/import_my_office_assets.py <zip> mobile/public/assets/my-office")
    try:install(sys.argv[1],sys.argv[2])
    except (ValueError,zipfile.BadZipFile) as e:raise SystemExit(str(e))
