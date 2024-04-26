FROM mediagis/nominatim:4.4 as build

FROM ubuntu:latest as python-build
RUN apt update && apt install -y python3 python3-pip python3-venv build-essential \
        libtbb-dev libboost-all-dev libicu-dev pkg-config git \
        zlib1g-dev gcc-9 cmake libbz2-dev lua5.3 liblua5.3-dev 
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 100

RUN python3 -m venv venv
ENV PATH="/venv/bin:$PATH"
COPY ./app/requirements.txt ./requirements.txt
RUN pip install -r ./requirements.txt

FROM public.ecr.aws/lambda/python:3.10-x86_64

# copy nominatim binaries
COPY --from=build /usr/local/bin/nominatim /usr/local/bin/nominatim
COPY --from=build /usr/local/share/nominatim /usr/local/share/nominatim
COPY --from=python-build /venv /venv

ENV PATH="/venv/bin:$PATH"

# set pythonpath to include nominatim
ENV PYTHONPATH=/usr/local/share/nominatim/lib-python:$PYTHONPATH

COPY ./app ./app
CMD ["app.main.handler"]
