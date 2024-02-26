package org.dice_research.hobbit.example.aiws24;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Random;
import java.util.concurrent.Semaphore;

import org.apache.commons.io.FileUtils;
import org.apache.jena.rdf.model.Model;
import org.apache.jena.rdf.model.ModelFactory;
import org.apache.jena.rdf.model.Resource;
import org.hobbit.core.Commands;
import org.hobbit.core.Constants;
import org.hobbit.core.components.AbstractBenchmarkController;
import org.hobbit.core.rabbit.DataHandler;
import org.hobbit.core.rabbit.DataReceiver;
import org.hobbit.core.rabbit.DataReceiverImpl;
import org.hobbit.core.rabbit.DataSender;
import org.hobbit.core.rabbit.DataSenderImpl;
import org.hobbit.core.rabbit.RabbitMQUtils;
import org.hobbit.utils.rdf.RdfHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class BenchmarkController extends AbstractBenchmarkController {

    private static final Logger LOGGER = LoggerFactory.getLogger(BenchmarkController.class);

    public static final byte LEARNING_FINISHED_COMMAND = 101;
    public static final double TRAIN_DATA_AMOUNT = 0.9;

    public static final String DATA_DIRECTORY = "/data/";
    public static final String FILE_CSV_SEPARATOR = ";";
    public static final String MESSAGE_CSV_SEPARATOR = ";";
    public static final String BENCHMARK_NAMESPACE = "http://example.org/ai-winter-school-2024/benchmark/";

    protected Long seed = null;
    protected File datasetFile = null;
    protected String dataHeaderLine = null;
    protected List<String> trainData = null;
    protected List<String> testData = null;
    protected long[] timestampsSent = null;
    protected Map<Integer, Long> timestampsReceived = new HashMap<>();
    protected Map<Integer, Double> receivedAnswers = new HashMap<>();
    protected int nextTaskId = 0;
    /*
     * The following attributes are for the internal workflow and can be mainly
     * ignored.
     */
    protected DataSender trainingDataSender;
    protected DataSender testDataSender;
    protected DataReceiver answerReceiver;
    protected Semaphore systemFinishedLearningMutex = new Semaphore(0);
    protected Semaphore allAnswersReceivedMutex = new Semaphore(0);

    @Override
    public void init() throws Exception {
        super.init();
        // Read parameters
        Resource dataset = RdfHelper.getObjectResource(benchmarkParamModel, null,
                benchmarkParamModel.getProperty(BENCHMARK_NAMESPACE + "dataset"));
        if (dataset == null) {
            throw new IllegalStateException("Couldn't get dataset IRI from parameter model.");
        }
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
        seed = RdfHelper.getLongValue(benchmarkParamModel, null,
                benchmarkParamModel.getProperty(BENCHMARK_NAMESPACE + "seed"));
        if (seed == null) {
            throw new IllegalStateException("Couldn't get seed from parameter model.");
        }

        // Set up additional communication
        initCommunication();
    }

    @Override
    protected void executeBenchmark() throws Exception {
        // Load and split data
        loadAndSplitData();
        // Send training data
        sendTrainingData();
        // Wait for the system to finish its learning phase before telling the task
        // generator to start
        waitForSystemToFinishLearning();
        // Start sending tasks by sending the first one...
        sendNextTask();
        // Wait for the tasks to finish.
        waitForTasksToFinish();
        // Let the system know that we are done
        sendTasksFinished();
        // Run evaluation
        evaluate();
        // Send the resultModul to the platform controller and terminate
        sendResultModel(resultModel);
        LOGGER.info("Result model has been submitted. I am done.");
    }

    protected void loadAndSplitData() throws IOException {
        List<String> lines = FileUtils.readLines(datasetFile);
        dataHeaderLine = lines.get(0);
        // sample data
        trainData = new ArrayList<>();
        testData = new ArrayList<>();
        Random rng = new Random(seed);
        String line;
        for (int i = 1; i < lines.size(); ++i) {
            line = lines.get(i);
            if (!line.trim().isEmpty()) {
                if (rng.nextDouble() < TRAIN_DATA_AMOUNT) {
                    trainData.add(line);
                } else {
                    testData.add(line);
                }
            }
        }
        timestampsSent = new long[testData.size()];
    }

    protected void sendTrainingData() throws IOException {
        StringBuilder trainingData = new StringBuilder(dataHeaderLine);
        // Add separator to insert a column for the line IDs
        trainingData.append(MESSAGE_CSV_SEPARATOR);
        trainingData.append(dataHeaderLine);
        for (int i = 0; i < trainData.size(); ++i) {
            trainingData.append('\n');
            // Training data should be preceded with the ID of the line within the training
            // data
            trainingData.append(i);
            trainingData.append(MESSAGE_CSV_SEPARATOR);
            trainingData.append(trainData.get(i));
        }
        trainingDataSender.sendData(RabbitMQUtils.writeString(trainingData.toString()));
    }

    protected void sendNextTask() throws IOException {
        if (nextTaskId < testData.size()) {
            // Create next task
            StringBuilder taskData = new StringBuilder();
            taskData.append(MESSAGE_CSV_SEPARATOR);
            taskData.append(dataHeaderLine);
            taskData.append('\n');
            taskData.append(nextTaskId);
            taskData.append(MESSAGE_CSV_SEPARATOR);
            // Remove last part of the line representing the current task
            String line = testData.get(nextTaskId);
            int pos = line.lastIndexOf(FILE_CSV_SEPARATOR);
            if (pos >= 0) {
                line = line.substring(0, pos);
                // If the two CSVs have different separators, replace them.
                if (!MESSAGE_CSV_SEPARATOR.equals(FILE_CSV_SEPARATOR)) {
                    line = line.replaceAll(FILE_CSV_SEPARATOR, MESSAGE_CSV_SEPARATOR);
                }
                taskData.append(line);
                // Send next task
                testDataSender.sendData(RabbitMQUtils.writeString(taskData.toString()));
                timestampsSent[nextTaskId] = System.currentTimeMillis();
                // Increase task ID
                ++nextTaskId;
            } else {
                // In case of an error with the test data
                LOGGER.error("task with ID {} is faulty (\"{}\"). Sending next task.", nextTaskId, line);
                ++nextTaskId;
                sendNextTask();
            }
        } else {
            // Let the main thread know that we got all the answers
            allAnswersReceivedMutex.release();
        }
    }

    protected void handleSystemAnswer(byte[] data) {
        // Process the answer that we received
        try {
            long timestamp = System.currentTimeMillis();
            String answer = RabbitMQUtils.readString(data);
            Objects.nonNull(answer);
            String[] answerParts = answer.split(MESSAGE_CSV_SEPARATOR);
            if (answerParts.length > 1) {
                // Parse the two parts of the answer and add it to the set of received answers
                Integer taskId = Integer.parseInt(answerParts[0]);
                receivedAnswers.put(taskId, Double.parseDouble(answerParts[1]));
                timestampsReceived.put(taskId, timestamp);
            } else {
                LOGGER.warn("Got a malformed answer that couldn't be split \"{}\".", answer);
            }
        } catch (Exception e) {
            LOGGER.warn("Exception while processing answer. Moving on.", e);
        }
        // Send next task
        try {
            sendNextTask();
        } catch (IOException e) {
            // Hard reaction, but maybe the best we can do here...
            LOGGER.error("Exception while sending next task. I will shut down myself.", e);
            System.exit(1);
        }
    }

    protected void evaluate() {
        LOGGER.info("Evaluating answers...");
        // Evaluate answers
        String line;
        int pos;
        double expectedValue;
        double receivedValue;
        for (int i = 0; i < testData.size(); ++i) {
            try {
                line = testData.get(i);
                pos = line.lastIndexOf(FILE_CSV_SEPARATOR);
                if (pos >= 0) {
                    line = line.substring(pos + FILE_CSV_SEPARATOR.length()).trim();
                    if (!line.isEmpty()) {
                        expectedValue = Double.parseDouble(line);
                        if (receivedAnswers.containsKey(i)) {
                            receivedValue = receivedAnswers.get(i);
                            // Here, we could add some evaluation checking whether the received value fits
                            // to the expected value.
                        }
                    }
                }
            } catch (NumberFormatException e) {
                LOGGER.error("Exception when parsing the expected answer of task " + i + ". It will be ignored.", e);
            }
        }
        // Evaluate runtimes
        List<Long> runtimes = timestampsReceived.entrySet().stream().filter(e -> e.getKey() < timestampsSent.length)
                .map(e -> e.getValue() - timestampsSent[e.getKey()]).toList();
        double avgRuntime = runtimes.stream().mapToLong(l -> l).average().orElse(Double.NaN);
        double stdDevRuntime = Math
                .sqrt(runtimes.stream().mapToDouble(l -> Math.pow(avgRuntime - l, 2)).average().orElse(Double.NaN));
        // Create result model and send it
        Model resultModel = ModelFactory.createDefaultModel();
        Resource experiment = resultModel.getResource(experimentUri);
        resultModel.addLiteral(experiment, resultModel.getProperty(BENCHMARK_NAMESPACE + "avgRuntime"), avgRuntime);
        resultModel.addLiteral(experiment, resultModel.getProperty(BENCHMARK_NAMESPACE + "stdDevRuntime"),
                stdDevRuntime);
        resultModel.addLiteral(experiment, resultModel.getProperty(BENCHMARK_NAMESPACE + "testDataSize"),
                (long) testData.size());
        resultModel.addLiteral(experiment, resultModel.getProperty(BENCHMARK_NAMESPACE + "faultyResponses"),
                (long) (timestampsSent.length - timestampsReceived.size()));

        setResultModel(resultModel);
    }

    /*
     * From here on, the implementation focuses on the setup of the communication
     * and the general workflow. It might not be too interesting for the beginning.
     */

    protected void waitForTasksToFinish() {
        LOGGER.info("Waiting for the benchmarked system to answer all tasks.");
        try {
            allAnswersReceivedMutex.acquire();
        } catch (InterruptedException e) {
            String errorMsg = "Interrupted while waiting for the benchmarked system  to answer all tasks.";
            LOGGER.error(errorMsg);
            throw new IllegalStateException(errorMsg, e);
        }
    }

    protected void waitForSystemToFinishLearning() {
        LOGGER.info("Waiting for the benchmarked system to finish its learning phase.");
        try {
            systemFinishedLearningMutex.acquire();
        } catch (InterruptedException e) {
            String errorMsg = "Interrupted while waiting for the benchmarked system to finish its learning phase.";
            LOGGER.error(errorMsg);
            throw new IllegalStateException(errorMsg, e);
        }
    }

    protected void sendTasksFinished() {
        try {
            sendToCmdQueue(Commands.TASK_GENERATION_FINISHED);
        } catch (IOException e) {
            String errorMsg = "Couldn't send the " + Commands.TASK_GENERATION_FINISHED + " command. Aborting.";
            LOGGER.error(errorMsg);
            throw new IllegalStateException(errorMsg, e);
        }
    }

    @Override
    public void receiveCommand(byte command, byte[] data) {
        if (command == LEARNING_FINISHED_COMMAND) {
            // The system finished its learning
            systemFinishedLearningMutex.release();
        } else {
            // Give the command to the super class
            super.receiveCommand(command, data);
        }
    }

    private void initCommunication() throws IllegalStateException, IOException {
        trainingDataSender = DataSenderImpl.builder().queue(getFactoryForOutgoingDataQueues(),
                generateSessionQueueName(Constants.DATA_GEN_2_SYSTEM_QUEUE_NAME)).build();
        testDataSender = DataSenderImpl.builder().queue(getFactoryForOutgoingDataQueues(),
                generateSessionQueueName(Constants.TASK_GEN_2_SYSTEM_QUEUE_NAME)).build();
        answerReceiver = DataReceiverImpl.builder().dataHandler(new DataHandler() {
            @Override
            public void handleData(byte[] data) {
                handleSystemAnswer(data);
            }
        }).maxParallelProcessedMsgs(1).queue(getFactoryForIncomingDataQueues(),
                generateSessionQueueName(Constants.SYSTEM_2_EVAL_STORAGE_DEFAULT_QUEUE_NAME)).build();
    }

    @Override
    public void close() throws IOException {
        trainingDataSender.close();
        testDataSender.close();
        answerReceiver.closeWhenFinished();
        // Always close the super class after yours!
        super.close();
    }

}