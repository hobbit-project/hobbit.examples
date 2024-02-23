# AI Winter School 2024 – Evaluating Machine Learning

This directory contains is used for the [AI Winter School 2024](https://indico.uni-paderborn.de/event/62/). It comes with a pre-configured HOBBIT platform deployment for local development as well as a very basic benchmark and baseline system implementation for Java and Python, respectively.

## Scenario and Benchmark Design

The target of this tutorial is to implement a benchmark for a regression task. As example, we use the [🍷 wine quality dataset](https://archive.ics.uci.edu/dataset/186/wine+quality) of [Cortez et al](https://repositorium.sdum.uminho.pt/bitstream/1822/10029/1/wine5.pdf). In the following, we will briefly look at the data, define the task that a benchmarked system should fulfill and design of the benchmark and its API.

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

### System's Task

We define the task that a system, which will be evaluated with our benchmark, should fulfill as a regression. The target values are the quality levels 0 (very bad) to 10 (excellent). Note that the data itself only contains labels ranging from 3 to 9 and that the data is unbalanced, i.e., the most wines belong to the quality levels 5, 6 or 7.

We further want to enable the usage of supervised machine learning. Hence, our benchmark has to ensure that the data is split into training and test data. The training data has to be made available for the system to train an algorithm. Further, we define that the split should be done randomly and that 90% of the data should be used for training.

The benchmark should measure the effectiveness and efficiency of a system. While the effectiveness can be measured with a large number of different measures, we focus on the usage of Micro Precision, Recall and F1-measure. The efficiency should be measured in form of the time that the system needs to classify the single examples.

### Benchmark Design

A major part of the work on a benchmark is to define its internal workflow and the API that the system has to implement to be evaluated by the benchmark. For this example, we use a quite simple setup with only two containers—a benchmark and a system container. In addition to the [general API of the HOBBIT platform](system_integration_api.html) that has to be implemented by the system, the benchark's API comprises the following parts:
1. The task definition above already stated that the data has to be split to get training and test data. We define that 10% of the dataset are randomly chosen as test dataset. The remaining 90% are used as training data and are sent to the system at the beginning as a CSV file of the form above.
2. The system should have the time to train an internal algorithm using the training data. Hence, the evaluation of the system should only start after the system signalled that the internal training has finished and that it is ready to be benchmarked.
3. The benchmark will sent the single tasks (i.e., the instances of the test set) as CSV comprising the headline and a single data line. The first column of the line contains the ID of the task, which has to be part of the response. The column with the quality level is removed before submission.
4. The system is expected to send a single CSV line comprising two values: Firstly, the task ID. Secondly, the value that it predicts for the task.

Our benchmark will have several parameters:
* **Dataset**: There are two wine datasets. One for red and a second for white wine. The user should be able to choose which dataset they want to use.
* **Seed**: The split into train and test data will be done randomly. However, the user should be able to define a seed value to ensure that an experiment is repeatable.
* **Test dataset size**: The benchmark should report the size of the randomly created test dataset.

The benchmark should provide the following evaluation results (also called key performance indicators (KPIs)):
* **Runtime**: The average runtime that the system needs to answer a request (including its standard deviation).
* **Faulty responses**: The number of faulty responses that the system may have produced. This avoids to include them into the error calculation and allows the benchmark to report that the system did not always create correctly formed answers.

The figure below gives an overview of the benchmark and its components as well as the type of data that they send to each other.

<p align="center">
  <img src="/images/Components-diagram-wine-benchmark.svg" />
</p>

## Prerequisites

The following software has to be available on the machine on which the platform should be run:

* [Docker](https://www.docker.com/) 19.03.13 or newer
* [Docker Compose](https://docs.docker.com/compose/) 1.19.0 or newer

In addition, an editor for developing Java or Python programs should be available. Additionally, [make](https://www.gnu.org/software/make/manual/html_node/index.html) can be helpful since we provide a Makefile that eases the execution of commands.

## Preparations

You should download / checkout this directory. Within this directory, we already prepared the HOBBIT platform in a local, development-friendly setup for you. Before starting the HOBBIT platform, you should run the following two commands once:
```sh
docker swarm init
make create-networks
```
The first will initialize the swarm mode of Docker. The second will create three Docker overlay networks, which are needed for the components to talk to each other later on.

### HOBBIT Platform

After the initialization above, the platform can be started with:
```sh
make start-hobbit-platform
```
After that, you can find the user interface (UI) of the platform at [http://localhost:8080].

The platform can also be stopped with:
```sh
make stop-hobbit-platform
```

The Platform runs in develop mode. This ensures that you can access Docker containers of the benchmark and system even after they terminated. However, that also means that some of them might be still running. If you want to easily remove containers created by the platform (without stopping the platform itself), you can do that with the following command:
```sh
make remove-hobbit-containers
```
Note that this will also remove containers of a currently running experiment. So please only use it if you are sure that you do not need any of the containers anymore.

### Benchmark and System

We prepared two base implementations for the benchmark and system, respectively. One implementation is in Java and a second in Python. You will find them in the `java` and `python` directories. At the beginning, you may want to build them, to ensure that the build itself works and that you can run them on your local HOBBIT platform.
```sh
make build-java
make build-python
```
After that, you can start an experiment by clicking on `Benchmarks` in the HOBBIT UI, choosing one of the benchmarks and one of the systems and pressing `Submit`.

## Tasks

There are several improvements possible. Note that all of them can be either done with Java or Python. It is mainly up to you which language you prefer. You can also create teams with other students to work on several tasks in parallel, e.g., implement more systems and more KPIs to compare them.

### Add a new KPI

The current benchmark implementation does not measure the quality of the results. The goal of this task is to add at least one KPI that does this.

#### Implementation

TODO

#### Meta Data Update

TODO

### Add a System

TODO

#### Meta Data Update

TODO

### Dataset Extension

The current imeplementation contains only the two wine-related datasets of Cortez et al. However, there are other interesting datasets for regression available. If you find such an example (e.g., at https://archive.ics.uci.edu/) you can integrate it into the benchmark.

In the following, we will assume that we have found a dataset about weather, in which a regression should predict the amount of rain that falls on a certain day based on additional data (air pressure, temperature, etc.). The dataset comprises a single file named `rain.dat`.

#### Data Files

First, you should move the file(s) of the new dataset into the `data` directory. This directory will be copied into the benchmark and available as `/data` directory.

In our example, we move `rain.dat` to `data/rain.dat`.

#### Meta Data Update

Depending on whether you prefer to program in Java or Python, you should open either `meta/ai-ws-2024-benchmark-java.ttl` or `ai-ws-2024-benchmark-python.ttl`. In both files, you will find the following lines:
```turtle
:CortezRed a :WineDataset;
  rdfs:label "Red wine"@en;
  rdfs:comment "The red wine dataset proposed by Cortez et al."@en .
```
We can simply copy these lines into the same file and adapt them to our needs. In our example, we could define our dataset as follows:
```diff
 :CortezRed a :WineDataset;
   rdfs:label "Red wine"@en;
   rdfs:comment "The red wine dataset proposed by Cortez et al."@en .
+
+:RainForecast a :WineDataset;
+  rdfs:label "Rain forecast"@en;
+  rdfs:comment "A dataset about forecasting the amount of rain that will fall on a particular day."@en .
```
Note that with this line, we defined the label and description of our dataset as well as an IRI: `http://example.org/ai-winter-school-2024/benchmark/RainForecast`.

#### Implementation

Finally, we should implement a piece of code that loads the data. We suggest to keep the API of the benchmark as it is, i.e., it would be best to load the data and transform it into the same CSV format that is already used. However, this step depends a lot on the new dataset. Hence, we cannot give an exact example what has to be implemented but we can point out where it should be implemented.

##### Java
If you use Java, you should have a look at the `init` method of the [BenchmarkController class](https://github.com/hobbit-project/hobbit.examples/blob/main/AI-winter-school-2024/java/benchmark/src/main/java/org/dice_research/hobbit/example/aiws24/BenchmarkController.java):
```java
        String datasetFileName = null;
        switch (dataset.getURI()) {
        case "http://example.org/ai-winter-school-2024/benchmark/CortezRed": {
            datasetFileName = "winequality-red.csv";
            break;
        }
        case "http://example.org/ai-winter-school-2024/benchmark/CortezWhite": {
            datasetFileName = "winequality-white.csv";
            break;
        }
        default: {
            LOGGER.error("Unknown dataset IRI {}", dataset.getURI());
            throw new IllegalStateException("Couldn't get dataset file name from parameter model.");
        }
        }
        datasetFile = new File(DATA_DIRECTORY + datasetFileName);
```
You should add the IRI of your new dataset to the switch case statement above to set the name of your file. In our example, we could add:
```java
        case "http://example.org/ai-winter-school-2024/benchmark/RainForecast": {
            datasetFileName = "rain.dat";
            break;
        }
```
We also have to ensure that loading the data is adapted. This should be done at the `loadAndSplitData` method:
```java
    protected void loadAndSplitData() throws IOException {
        List<String> lines = FileUtils.readLines(datasetFile);
```
The first line of the method loads the lines of a CSV file. As described above, depending on the new dataset file structure, we suggest to implement the loading in a way that it creates CSV lines of the same structure and provides them as a list of Strings (e.g., as `List<String> lines`).

##### Python

If you use Python, you should have a look at the `prepare_data` method of the [benchmark.py](https://github.com/hobbit-project/hobbit.examples/blob/main/AI-winter-school-2024/python/benchmark/benchmark.py):
```python
    def prepare_data(self):
        """
        Load dataset and split it into train and test.
        """
        data_file = None
        if (BENCHMARK_NAMESPACE + "CortezRed").__eq__(self.dataset_iri):
            data_file = DATA_FOLDER_PATH + "winequality-red.csv"
        elif (BENCHMARK_NAMESPACE + "CortezWhite").__eq__(self.dataset_iri):
            data_file = DATA_FOLDER_PATH + "winequality-white.csv"
        else:
            logger.error(f"Unknown dataset IRI {self.dataset_iri}.")
            raise AttributeError()
        # Load file
        data = pd.read_csv(data_file, sep=FILE_CSV_SEPARATOR)
```
You should add the IRI of your new dataset in an additional `elif` clause to set the name of your file. In our example, we could add:
```python
        elif (BENCHMARK_NAMESPACE + "RainForecast").__eq__(self.dataset_iri):
            data_file = DATA_FOLDER_PATH + "rain.dat"
```
We also have to ensure that loading the data is adapted. This is currently done in the last line of the previous excerpt, which loads the data from a CSV file using the pandas library. As described above, depending on the new dataset file structure, we suggest to implement the loading in a way that it creates a pandas data frame of the same structure as it would have if we would use the CSV files.

