FROM alpine:latest

RUN apk add --no-cache apache2 php83 php83-apache2 \
    && sed -i 's#^Listen 80#Listen 8080#' /etc/apache2/httpd.conf \
    && echo "ServerName localhost" >> /etc/apache2/httpd.conf

# Set the working directory
WORKDIR /var/www/localhost/htdocs

# Remove default index file
RUN rm -f /var/www/localhost/htdocs/index.html
# Copy application files
# Ensure 'includes', 'js', 'assets', 'style.css', 'index.php' exist in the build context
COPY src/index.php .
COPY src/style.css .
COPY src/includes/ /var/www/localhost/htdocs/includes/
COPY src/js/ /var/www/localhost/htdocs/js/
COPY src/assets/ /var/www/localhost/htdocs/assets/

# Optional: Set permissions if needed (Apache runs as www-data by default)
# RUN chown -R www-data:www-data /var/www/html

# Expose port 8080
EXPOSE 8080

CMD ["/usr/sbin/httpd", "-D", "FOREGROUND"]
