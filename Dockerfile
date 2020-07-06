FROM python:2.7.9

#RUN apt-get install -y software-properties-common && add-apt-repository -y ppa:ubuntu-toolchain-r/test

RUN apt-get update \
    && apt-get install -y \
        checkinstall \
        gettext \
        libgeos-dev \
        libproj-dev \
        libgdal1-dev \
        build-essential \
        python-dev \
        python-pip \
        libfreetype6-dev \
        curl

RUN curl -sL https://deb.nodesource.com/setup_8.x | bash - && apt-get install -y nodejs

RUN npm install -g yarn

WORKDIR /usr/local/otm/app
COPY . . 

RUN pip install -r requirements.txt \
    && pip install -r dev-requirements.txt \
    && pip install -r test-requirements.txt

RUN mkdir -p /usr/local/otm/static && mkdir -p /usr/local/otm/media

# Bundle JS and CSS via webpack
RUN yarn --force
