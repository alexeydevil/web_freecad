# trigger build 
FROM ubuntu:16.04

USER root

ENV CXX=g++-8
ENV CC=gcc-8

ENV PYTHON_VERSION 3.5.2
ENV PYTHON_MINOR_VERSION 3.5
ENV PYTHON_SUFFIX_VERSION .cpython-35m
ENV PYTHON_BIN_VERSION python3.5m
ENV PYTHON_PIP_VERSION 19.0

######################
# start packages #
######################
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:ubuntu-toolchain-r/test
RUN apt-get update
RUN apt-get install -y \
    python$PYTHON_MINOR_VERSION \
    python$PYTHON_MINOR_VERSION-dev \
    wget \
    git \
    build-essential \
    libgl1-mesa-dev \
    libfreetype6-dev \
    libglu1-mesa-dev \
    libzmq3-dev \
    libsqlite3-dev \
    libboost-all-dev \
    libicu-dev \
    libgl2ps-dev \
    libfreeimage-dev \
    libtbb-dev \
    g++-8 \
    libopenblas-dev \
    cmake \
    swig \
    ninja-build \
    xvfb \
    gtk+-3.0 \
    libgstreamer-plugins-base1.0-dev \
    python3-pip

RUN pip3 install pip --upgrade
RUN pip3 install wxpython
RUN pip3 install PyVirtualDisplay


#######
# OCE #
#######
WORKDIR /opt/build
RUN git clone https://github.com/tpaviot/oce
RUN mkdir oce/build && mkdir oce/install
WORKDIR /opt/build/oce/build
RUN git checkout OCE-0.18.3

RUN cmake -G Ninja \
 -DCMAKE_BUILD_TYPE=Release \
 -DOCE_TESTING:BOOL=OFF \
 -DOCE_BUILD_SHARED_LIB:BOOL=ON \
 -DOCE_VISUALISATION:BOOL=ON \
 -DOCE_DATAEXCHANGE:BOOL=ON \
 -DOCE_OCAF:BOOL=ON \
 -DOCE_DRAW:BOOL=OFF \
 -DOCE_WITH_GL2PS:BOOL=ON \
 -DOCE_WITH_FREEIMAGE:BOOL=ON \
 -DOCE_MULTITHREAD_LIBRARY:STRING="TBB" \
 -DOCE_INSTALL_PREFIX=/usr/local/share/oce \
 ..

RUN ninja install

RUN echo "/usr/local/share/oce/lib" >> /etc/ld.so.conf.d/pythonocc.conf
RUN ldconfig
RUN cp -R /usr/local/share/oce/share/oce-0.18/src/ /usr/local/share/oce/

#########
# smesh #
#########
WORKDIR /opt/build
RUN git clone https://github.com/tpaviot/smesh
RUN mkdir smesh/build && mkdir smesh/install
WORKDIR /opt/build/smesh/build
RUN git checkout 6.7.6

RUN cmake -G Ninja \
 -DCMAKE_BUILD_TYPE=Release \
 -DSMESH_TESTING:BOOL=OFF \
 -DOCE_INCLUDE_PATH=/usr/local/share/oce/include/oce \
 -DOCE_LIB_PATH=/usr/local/share/oce/lib \
 -DCMAKE_INSTALL_PREFIX=/usr/local/share/smesh \
 ..

RUN ninja install

RUN echo "/usr/local/share/smesh/lib" >> /etc/ld.so.conf.d/smesh.conf
RUN ldconfig

########
# gmsh #
########
ENV CASROOT=/usr/local/share/oce
WORKDIR /opt/build
RUN git clone https://gitlab.onelab.info/gmsh/gmsh
WORKDIR /opt/build/gmsh
RUN git checkout gmsh_4_0_7
WORKDIR /opt/build/gmsh/build

RUN cmake -G Ninja \
 -DCMAKE_BUilD_TYPE=Release \
 -DENABLE_OCC=ON \
 -DENABLE_OCC_CAF=ON \
 -DCMAKE_INSTALL_PREFIX=/usr/local/share/gmsh \
 ..

RUN ninja install

#############
# pythonocc #
#############
WORKDIR /opt/build
RUN git clone https://github.com/tpaviot/pythonocc-core
WORKDIR /opt/build/pythonocc-core
RUN git submodule update --init --remote --recursive
WORKDIR /opt/build/pythonocc-core/build

RUN cmake -G Ninja \
 -DPYTHON_EXECUTABLE:PATH=/usr/lib/$PYTHON_BIN_VERSION \
 -DPYTHON_INCLUDE_DIR:PATH=/usr/include/$PYTHON_BIN_VERSION \
 -DPYTHON_LIBRARY:PATH=/usr/lib/x86_64-linux-gnu/lib${PYTHON_BIN_VERSION}.so \
 -DPYTHONOCC_INSTALL_DIRECTORY:PATH=/usr/lib/python$PYTHON_MINOR_VERSION/dist-packages/OCC  \
 -DPYTHONOCC_BUILD=Release \
 -DPYTHONOCC_WRAP_OCAF=ON \
 -DPYTHONOCC_WRAP_SMESH=ON \
 -DOCE_INCLUDE_PATH=/usr/local/share/oce/include/oce \
 -DOCE_LIB_PATH=/usr/local/share/oce/lib \
 -DSMESH_INCLUDE_PATH=/usr/local/share/smesh/include/smesh \
 -DSMESH_LIB_PATH=/usr/local/share/smesh/lib \
 ..
 
RUN ninja install


#######################
# create microservice #
#######################
WORKDIR /opt/webcad_service
COPY http_server.py /opt/webcad_service/http_server.py
COPY opencad_wrapper.py /opt/webcad_service/opencad_wrapper.py
