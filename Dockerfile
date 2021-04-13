FROM python:3.8

#RUN apt-get install -y software-properties-common && add-apt-repository -y ppa:ubuntu-toolchain-r/test

#checkinstall \
#libgdal1-dev \

RUN apt-get update \
    && apt-get install -y \
        gettext \
        libgeos-dev \
        libproj-dev \
        build-essential \
        python3-dev \
        python3-pip \
        libfreetype6-dev \
        binutils \
        libproj-dev \
        gdal-bin \
        curl

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash - && apt-get install -y nodejs

RUN npm install -g yarn

WORKDIR /usr/local/otm/app
# only copy what we need
COPY requirements.txt .
RUN pip install -r requirements.txt
# Bundle JS and CSS via webpack
RUN yarn --force

# then copy everything else
COPY . . 
COPY docker/local_settings.py /usr/local/otm/app/opentreemap/opentreemap/settings/local_settings.py 

RUN mkdir -p /usr/local/otm/static && mkdir -p /usr/local/otm/media && mkdir -p /usr/local/otm/emails
