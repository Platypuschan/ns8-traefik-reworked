#!/bin/bash

set -e
images=()
repobase="${REPOBASE:-ghcr.io/platypuschan}"

reponame="traefik-reworked"
container=$(buildah from scratch)

buildah add "${container}" imageroot /imageroot
buildah add "${container}" ui /ui
# Traefik v3.7.17 OCI index (all supported platforms), verified with skopeo --raw.
buildah config --entrypoint=/ \
    --label="org.nethserver.images=docker.io/traefik@sha256:f4bb143d1135a579b630ed491e17ec50f6f7c9c6a30585ff3d385471d2a86f5a" \
    --label="org.nethserver.flags=core_module" \
    --label="org.opencontainers.image.source=https://github.com/Platypuschan/ns8-traefik-reworked" \
    --label="org.nethserver.min-core=3.17.0-0" \
    "${container}"
buildah commit "${container}" "${repobase}/${reponame}"
images+=("${repobase}/${reponame}")

#
# Setup CI when pushing to Github. 
# Warning! docker::// protocol expects lowercase letters (,,)
#
if [[ -n "${GITHUB_OUTPUT}" ]]; then
    # Set output value for Github Actions
    printf "images=%s\n" "${images[*],,}" >> "${GITHUB_OUTPUT}"
    printf " - %s:${IMAGETAG:-latest}\n" "${images[@],,}" >> $GITHUB_STEP_SUMMARY
else
    # Just print info for manual push
    printf "Publish the images with:\n\n"
    for image in "${images[@],,}"; do printf "  buildah push %s docker://%s:%s\n" "${image}" "${image}" "${IMAGETAG:-latest}" ; done
    printf "\n"
fi
