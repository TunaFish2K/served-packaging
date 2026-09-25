FROM archlinux:base-devel
RUN sed -i '/^NoExtract/d' /etc/pacman.conf \
    && pacman -Syu --noconfirm --needed python namcap man-db systemd openssh shellcheck \
    && useradd -m builder \
    && useradd -m alice \
    && useradd -m bob
CMD ["/usr/bin/bash"]
