# SAIL Winter School 2024 – Evaluating Machine Learning

This directory contains is used for the [SAIL Winter School 2024](https://indico.uni-paderborn.de/event/62/). It comes with a pre-configured HOBBIT platform deployment for local development as well as a very basic benchmark and baseline system implementation for Java and Python, respectively.

## Scenario and Benchmark Design

The target of this tutorial is to implement a benchmark for a regression task. As example, we use the [🍷 wine quality dataset](https://archive.ics.uci.edu/dataset/186/wine+quality) of Cortez et al. In the following, we will briefly look at the data, define the task that a benchmarked system should fulfill and design of the benchmark and its API.

### Data 

The dataset comprises two files. One file is for red, the second is for white wine. We will handle these two files as two distinct datasets. However, both of them have the same structure. They come as CSV files in the following form:
```
"fixed acidity";"volatile acidity";"citric acid";"residual sugar";"chlorides";"free sulfur dioxide";"total sulfur dioxide";"density";"pH";"sulphates";"alcohol";"quality"
7;0.27;0.36;20.7;0.045;45;170;1.001;3;0.45;8.8;6
6.3;0.3;0.34;1.6;0.049;14;132;0.994;3.3;0.49;9.5;6
8.1;0.28;0.4;6.9;0.05;30;97;0.9951;3.26;0.44;10.1;6
7.2;0.23;0.32;8.5;0.058;47;186;0.9956;3.19;0.4;9.9;6
```
The structure of the file will be important later on. At the moment, it is sufficient to recognize that the file contains several features in a tabular format and that the last column contains the `"quality"`. This is the target value, that a system should predict.

### Task

We define the task that a system, which will be evaluated with our benchmark, should fulfill is defined as a regression. The target value are the quality levels 0 (very bad) to 10 (excellent). Note that the data itself only contains labels ranging from 3 to 9 and that the data is unbalanced, i.e., the most wines belong to the quality levels 5, 6 or 7.

We further want to enable the usage of supervised machine learning. Hence, our benchmark has to ensure that the data is split into training and test data. The training data has to be made available for the system to train an algorithm. Further, we define that the split should be done randomly and that 90% of the data should be used for training.

The benchmark should measure the effectiveness and efficiency of a system. While the effectiveness can be measured with a large number of different measures, we focus on the usage of Micro Precision, Recall and F1-measure. The efficiency should be measured in form of the time that the system needs to classify the single examples.

### Benchmark Design

A major part of the work on a benchmark is to define its internal workflow and the API that the system has to implement to be evaluated by the benchmark. We rely on the [suggested workflow of a benchmark](experiment_workflow.html). Hence, our benchmark implementation will comprise a Data Generator, a Task Generator, an Evaluation Storage, an Evaluation Module, and a Benchmark Controller. We will make use of a default implementation for the Evaluation Storage. All other components will be implemented within this tutorial.

In addition to the [general API of the HOBBIT platform](system_integration_api.html) that has to be implemented by the system, the benchark's API comprises the following parts:
1. The task definition above already stated that the data has to be split to get training and test data. We define that 10% of the dataset are randomly chosen as test dataset. The remaining 90% are used as training data and are sent to the system at the beginning as a CSV file of the form above, without the headline.
2. The system should have the time to train an internal algorithm using the training data. Hence, the evaluation of the system should only start after the system signalled that the internal training has finished and that it is ready to be benchmarked.
3. The benchmark will sent the single tasks (i.e., the instances of the test set) as CSV lines as above (without the quality column).

Our benchmark will have several parameters:
* **Dataset**: There are two wine datasets. One for red and a second for white wine. The user should be able to choose which dataset they want to use.
* **Seed**: The split into train and test data will be done randomly. However, the user should be able to define a seed value to ensure that an experiment is repeatable.
* **Test dataset size**: The benchmark should report the size of the randomly created test dataset.

The benchmark should provide the following evaluation results (also called key performance indicators (KPIs)):
* **MSE**: The mean squared error (MSE) that the benchmarked system achieves.
* **Runtime**: The average runtime that the system needs to answer a request (including its standard deviation).
* **Faulty responses**: The number of faulty responses that the system may have produced. This avoids to include them into the error calculation and allows the benchmark to report that the system did not always create correctly formed answers.

The figure below gives an overview of the benchmark and its components as well as the type of data that they send to each other.
In this tutorial, we will implement all components, except the Evaluation Storage for which we will reuse an existing implementation.

<p align="center">
  <img src="/images/Components-diagram-wine-benchmark.svg" />
</p>

## Prerequisites

The following software has to be available on the machine on which the platform should be run:

* [Docker](https://www.docker.com/) 19.03.13 or newer
* [Docker Compose](https://docs.docker.com/compose/) 1.19.0 or newer

In addition, an editor for developing Java or Python programs should be available. Additionally, [make](https://www.gnu.org/software/make/manual/html_node/index.html) can be helpful since we provide a Makefile that eases the execution of commands.

## Preparations

TODO

Run once:
docker swarm init
make create-networks

## Benchmark API

## Tasks

### Add a new KPI

#### Implementation

#### Meta Data update

### Add another System

#### Meta Data update

### Dataset Extension

Find a dataset, that fits to the task
https://archive.ics.uci.edu/
