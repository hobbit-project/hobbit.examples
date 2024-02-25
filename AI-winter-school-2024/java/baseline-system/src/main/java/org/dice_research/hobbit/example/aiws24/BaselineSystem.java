package org.dice_research.hobbit.example.aiws24;

import java.io.IOException;

import org.apache.commons.lang3.NotImplementedException;
import org.hobbit.core.Constants;
import org.hobbit.core.components.AbstractSystemAdapter;
import org.hobbit.core.rabbit.DataHandler;
import org.hobbit.core.rabbit.DataReceiverImpl;
import org.hobbit.core.rabbit.RabbitMQUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class BaselineSystem extends AbstractSystemAdapter {

    private static final Logger LOGGER = LoggerFactory.getLogger(BaselineSystem.class);

    public static final byte LEARNING_FINISHED_COMMAND = 101;
    public static final String MESSAGE_CSV_SEPARATOR = ";";

    protected double learnedValue = 0.0;

    @Override
    public void receiveGeneratedData(byte[] data) {
        String message = RabbitMQUtils.readString(data);
        String[] lines = message.split("\n");
        double sum = 0;
        int count = 0;
        int pos;
        for (int i = 1; i < lines.length; ++i) {
            pos = lines[i].lastIndexOf(MESSAGE_CSV_SEPARATOR);
            if (pos >= 0) {
                try {
                    sum += Double.parseDouble(lines[i].substring(pos + MESSAGE_CSV_SEPARATOR.length()));
                    ++count;
                } catch (NumberFormatException e) {
                    LOGGER.warn("Couldn't parse target value of a line: \"" + lines[i] + "\". It will be ignored.", e);
                }
            }
        }
        if (count > 0) {
            learnedValue = sum / count;
        } else {
            LOGGER.warn("Couldn't get any values to learn.");
        }
        try {
            sendToCmdQueue(LEARNING_FINISHED_COMMAND);
        } catch (IOException e) {
            LOGGER.error("Couldn't send message that the learning is finished. Aborting.", e);
            System.exit(1);
        }
    }

    /**
     * This method is called for each test data message received from the benchmark.
     * 
     * @param taskId  the ID of the task; it should simply be returned as part of
     *                the answer.
     * @param csvData the CSV data of the test case. <b>Note</b>: this data has
     *                already been pre-processed and comprises only the data values
     *                without headers and without the column containing the task ID.
     */
    public void receiveGeneratedTask(String taskId, String csvData) {
        // Here, we should use the data in csvData to predict. 
        // We should write the predicted value to the result variable:
        double result = learnedValue;
        
        // We will send the answer in the expected format. No need to change this.
        StringBuilder messageBuilder = new StringBuilder();
        messageBuilder.append(taskId);
        messageBuilder.append(MESSAGE_CSV_SEPARATOR);
        messageBuilder.append(Double.toString(result));
        try {
            sender2EvalStore.sendData(RabbitMQUtils.writeString(messageBuilder.toString()));
        } catch (IOException e) {
            LOGGER.error("Couldn't send answer. Aborting.", e);
            System.exit(1);
        }
    }

    /*
     * From here on, the implementation focuses on the setup of the communication
     * and the general workflow. It might not be too interesting for the beginning.
     */

    @Override
    public void init() throws Exception {
        super.init();
        this.taskGenReceiver.closeWhenFinished();
        taskGenReceiver = DataReceiverImpl.builder().maxParallelProcessedMsgs(1)
                .queue(incomingDataQueueFactory, generateSessionQueueName(Constants.TASK_GEN_2_SYSTEM_QUEUE_NAME))
                .dataHandler(new DataHandler() {
                    @Override
                    public void handleData(byte[] data) {
                        // We need to separate the task ID from the data...
                        String message = RabbitMQUtils.readString(data);
                        int startPos = message.indexOf('\n');
                        String taskId = null;
                        if (startPos >= 0) {
                            int endPos = message.indexOf(MESSAGE_CSV_SEPARATOR, startPos);
                            if (endPos >= 0) {
                                taskId = message.substring(startPos + 1, endPos);
                                message = message.substring(endPos + MESSAGE_CSV_SEPARATOR.length());
                            }
                        }
                        receiveGeneratedTask(taskId, message);
                    }
                }).build();
    }

    @Override
    public void receiveGeneratedTask(String taskId, byte[] data) {
        throw new NotImplementedException("This method shouldn't be called!");
    }

}
