# Simple CD Stripper

A simple python (using fpdf and flask) app to connect to discogs.com and download contents to build labels for a Jukebox.

Some docs in the [main_page](templates/main_page.html) HTML file.

You can see it in action at: https://simple-cd-stripper.roman-halliday.com/

Mostly built with AI/LLM development.

Inspired by my 7" labels project:
* https://simplestripper.roman-halliday.com/
* https://github.com/d-roman-halliday/simplestripper

## Deployment Notes - Apache WSGI

As I'm hosting this on apache (which always seems to be a battle with flask and painful to debug). I'm including my notes here.

create a `<site_dir>` under `/var/www/`, this can just be `simple_cd_stripper` (or just create straight under `/var/www/`) if you don't have other sites on the host, but it's nice (in my opinion) to keep the `venv` and the site together somewhere.

Note the difference between underscores and hyphens... The hostname (if using LetsEncrypt) can't contain underscores, so instead I'm using `simple-cd-stripper` for the hostname.

### Updates

Putting at the top as a reminder.

Update content, then reload `apache`.

```shell
cd /var/www/<site_dir>
cd simple_cd_stripper

git pull

# Or the changes won't show
sudo systemctl reload apache2
```

### Get files & setup venv

```shell
cd /var/www/<site_dir>

# Checkout project - updates can be gained with a pull command
git clone https://github.com/d-roman-halliday/simple_cd_stripper.git

# Setup venv
sudo python3 -m venv simple_cd_stripper_venv
sudo chown -R ${USER}:www-data simple_cd_stripper_venv

source simple_cd_stripper_venv/bin/activate
pip install -U pip
cd simple_cd_stripper
pip install -r requirements.txt
```

### Apache

#### Some basics

```shell
sudo a2enmod wsgi
```
#### Configure WSGI


```shell
cd /var/www/<site_dir>

sudo vim simple_cd_stripper/simple_cd_stripper.wsgi
sudo chown www-data:www-data simple_cd_stripper/simple_cd_stripper.wsgi
```

```
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/www/<site_dir>/simple_cd_stripper/")

from scs_flask_app import app as application
```

#### Configure VirtualHost

```shell
cd /etc/apache2/sites-available
sudo vim simple-cd-stripper.conf

sudo mkdir /var/log/apache2/simple_cd_stripper
sudo chown www-data:www-data /var/log/apache2/simple_cd_stripper
```

```
# Added to mitigate CVE-2017-8295 vulnerability
UseCanonicalName On

<VirtualHost *:80>
        ServerAdmin webmaster@localhost

        ServerName simple-cd-stripper.<hostname>

        DocumentRoot /var/www/roman-halliday.com/simple_cd_stripper/

        WSGIDaemonProcess simple_cd_stripper_n user=www-data group=www-data threads=5 python-home=/var/www/<site_dir>/simple_cd_stripper_venv
        WSGIProcessGroup simple_cd_stripper_n
        WSGIApplicationGroup %GLOBAL
        WSGIScriptAlias / /var/www/<site_dir>/simple_cd_stripper/simple_cd_stripper.wsgi

        <Directory /var/www/<site_dir>/simple_cd_stripper/>
            Options FollowSymLinks
            AllowOverride All
            Require all granted
        </Directory>

        ErrorLog ${APACHE_LOG_DIR}/simple_cd_stripper/error.log
        CustomLog ${APACHE_LOG_DIR}/simple_cd_stripper/access.log combined:q

</VirtualHost>
```

#### Try it

If you try to go to the website (providing this all worked), you will get notifications on security.

```shell
# Enable
sudo a2ensite simple-cd-stripper.roman-halliday.com.conf

# Disable
sudo a2dissite simple-cd-stripper.roman-halliday.com.conf


# Test config
sudo apachectl configtest

# Go
sudo systemctl reload apache2
# OR
sudo systemctl restart apache2
```

#### Secure it

 Made fun thanks to an old bug/behaviour.... https://github.com/certbot/certbot/issues/8373

In short, before doing this, go to the VirtualHost `simple-cd-stripper.conf` configuration file, and comment out `#` all the lines with `WSGI`. Or you will have an error from apache.

```shell
sudo certbot --apache
```

Now go to the new `simple-cd-stripper-le-ssl.conf`, and uncomment those lines.

And one last:
```shell
sudo systemctl reload apache2
# OR
sudo systemctl restart apache2
```