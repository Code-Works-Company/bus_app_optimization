FROM ubuntu:22.04

RUN apt update && apt install -y python3 python3-pip python3-venv build-essential \
        libtbb-dev libboost-all-dev libicu-dev pkg-config git zlib1g-dev gcc-9 cmake \ 
        libbz2-dev lua5.3 liblua5.3-dev default-jre
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 100

COPY ./requirements.txt ./requirements.txt

ENV PYTHONUNBUFFERED True
ENV PBF_PATH /custom_files/vietnam-latest.osm.pbf
COPY ./app ./app
COPY ./valhalla_data /custom_files
ADD https://github.com/komoot/photon/releases/download/0.5.0/photon-0.5.0.jar /photon.jar
ADD https://download1.graphhopper.com/public/extracts/by-country-code/vn/photon-db-vn-latest.tar.bz2 /photon_data.tar.bz2
RUN tar -xvf /photon_data.tar.bz2 -C /
COPY ./start.sh ./start.sh

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
# port 5000 for cloud run
ENV PORT 8000
ENV VALHALLA_DIR ./custom_files/valhalla_tiles.tar
ENV TIME_LIMIT 10

CMD /bin/bash ./start.sh
