FROM ubuntu:22.04

RUN apt update && apt install -y python3 python3-pip python3-venv build-essential \
        libtbb-dev libboost-all-dev libicu-dev pkg-config git zlib1g-dev gcc-9 cmake \ 
        libbz2-dev lua5.3 liblua5.3-dev default-jre
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 100

COPY ./app/requirements.txt ./requirements.txt

# set pythonpath to include nominatim
ENV PYTHONUNBUFFERED True
ENV PBF_PATH /custom_files/vietnam-latest.osm.pbf
COPY ./app ./app
COPY ./valhalla_data /custom_files
COPY ./photon.jar /photon.jar
COPY ./photon_data/ /photon_data
COPY ./start.sh ./start.sh

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
# port 5000 for cloud run
ENV PORT 5000

CMD /bin/bash ./start.sh
