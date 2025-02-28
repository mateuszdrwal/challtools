FROM php:apache

COPY index.php /var/www/html/
RUN chown -R root:root /var/www/html/

HEALTHCHECK --start-period=20s --start-interval=1s CMD curl -f http://127.0.0.1/ || exit 1
