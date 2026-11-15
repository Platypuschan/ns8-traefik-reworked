#!/bin/bash

set -e
images=()
repobase="${REPOBASE:-ghcr.io/platypuschan}"

reponame="traefik-reworked"
container=$(buildah from scratch)

buildah add "${container}" imageroot /imageroot
buildah add "${container}" ui /ui
# Traefik runtime: tag and OCI index digest (all supported platforms) are kept
# in sync by Renovate. The module label references the digest only.
TRAEFIK_IMAGE="docker.io/traefik:v3.7.19@sha256:aa942a00bce033c909bf1f7e861d93761be4b31a035f10d2410d33e38a8f41cf"
buildah config --entrypoint=/ \
    --label="org.nethserver.images=${TRAEFIK_IMAGE%%:*}@${TRAEFIK_IMAGE##*@}" \
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
