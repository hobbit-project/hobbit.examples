import logging  # for logging
import pika  # communication via RabbitMQ
import os  # used to access environmental variables
import time  # Used to sleep if necessary
import io  # Used for the writing of streams to String objects
import pandas as pd
from threading import Thread, Semaphore  # Threads and their synchronization

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the predefined command ID for SYSTEM_READY_SIGNAL
SYSTEM_READY_SIGNAL = 1
# Define the predefined command ID for TASK_GENERATION_FINISHED
TASK_GENERATION_FINISHED_SIGNAL = 15
# Define the predefined command ID for REPORT_ERROR
REPORT_ERROR_SIGNAL = 19
# The maximum number of attempts that are performed to connect to RabbitMQ
MAX_CONNECTION_ATTEMPTS = 5
# Time that the program waits between two connection attempts
SECONDS_BETWEEN_CONNECTION_ATTEMPTS = 5
# constants needed to communicate with the benchmark
LEARNING_FINISHED_SIGNAL = 101
MESSAGE_CSV_SEPARATOR = ';'


class SailWinterSchoolBaselineSystem:

    def __init__(self):
        self.session_id = os.getenv("HOBBIT_SESSION_ID")
        self.config = {
            "rabbitmq_host": os.getenv("HOBBIT_RABBIT_HOST", "localhost"),
            "rabbitmq_port": int(os.getenv("RABBITMQ_PORT", "5672")),
            #    "rabbitmq_user": os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
            #    "rabbitmq_pass": os.getenv("RABBITMQ_DEFAULT_PASS", "guest"),
            "train_queue_name": "hobbit.datagen-system." + self.session_id,
            "task_queue_name": "hobbit.taskgen-system." + self.session_id,
            "answer_queue_name": "hobbit.system-evalstore." + self.session_id,
            #    "command_queue_name": "hobbit.command_queue" + os.getenv("HOBBIT_SESSION_ID", ""),
            "system_model": os.getenv("SYSTEM_PARAMETERS_MODEL", "")
        }
        self.connection = None
        self.communication_mutex = Semaphore(value=0)
        self.termination_mutex = Semaphore(value=0)
        self.connection_attempt_counts = 0
        self.cmd_channel = None
        self.receiver_channel = None
        self.sender_channel = None
        self.logger = logging.getLogger(__name__)
        self.io_thread = None

        # Here, you can add more things that you may need for your prediction
        self.baseline_prediction = 0.0

    def process_train_data(self, data):
        """
        Process training data (e.g., train an internal model for prediction) and inform the benchmark as soon as the
        training is done.

        Args:
            data (str): The training data as CSV

        Returns:
            None
        """
        train_data = pd.read_csv(io.StringIO(data), sep=MESSAGE_CSV_SEPARATOR)
        # Here, we could implement a lot of fancy machine learning. This baseline simply determines the mean value that
        # it should predict.
        self.baseline_prediction = train_data[train_data.columns[len(train_data.columns) - 1]].mean()

        # Learning finished. Let's tell the Benchmark that we are ready to go
        self.send_command(LEARNING_FINISHED_SIGNAL)

    def process_task(self, task):
        """
        Process a task using the loaded machine learning model and send the result to the evaluation store.

        Args:
            task (str): The task as CSV line.

        Returns:
            None
        """
        try:
            task_data = pd.read_csv(io.StringIO(task), sep=MESSAGE_CSV_SEPARATOR)
            # The first cell contains the task ID (you may want to remove it before using the data!)
            task_id = task_data.iloc[0, 0]
            # Here, we can go crazy with the previous learned model. In this baseline, we simply send the result that
            # we already prepared
            answer = self.baseline_prediction

            # Send the answer to the evaluation store
            answer_message = f"{task_id}{MESSAGE_CSV_SEPARATOR}{answer}"
            self.sender_channel.basic_publish(exchange='',
                                              routing_key=self.config["answer_queue_name"],
                                              body=answer_message
                                              )

        except Exception as e:
            logging.exception(f"Error processing task: {e}")

    # ************************************************************************************************************
    # *** From here on, the implementation focuses on the setup of the communication and the general workflow. ***
    # *** It might not be too interesting for the beginning.                                                   ***
    # ************************************************************************************************************

    def setup_connection(self):
        """
        Set up a connection to RabbitMQ.

        Args:
            config (dict): Configuration settings.

        Returns:
            tuple: A tuple containing the RabbitMQ connection and channel.
        """

        def on_connected(new_connection):
            """Called when we are fully connected to RabbitMQ"""
            self.logger.info("Got a new connection.")
            self.connection = new_connection
            # self.connection_mutex.release()
            self.setup_channels()

        def on_connection_error(new_connection, exception):
            """Called when we are fully connected to RabbitMQ"""
            if self.connection_attempt_counts < MAX_CONNECTION_ATTEMPTS:
                self.logger.info("Got an error while waiting for the connection. Trying it again...")
                time.sleep(SECONDS_BETWEEN_CONNECTION_ATTEMPTS)
                self.connection = pika.SelectConnection(
                    parameters=pika.ConnectionParameters(self.config["rabbitmq_host"]),
                    on_open_callback=on_connected,
                    on_close_callback=stop_looping_on_close,
                    on_open_error_callback=on_connection_error
                )
            else:
                self.logger.exception(exception)
                self.connection = None
                # release four times for all four communication types
                self.communication_mutex.release()
                self.communication_mutex.release()
                self.communication_mutex.release()
                self.communication_mutex.release()

        self.logger.info("Trying to connect to " + self.config["rabbitmq_host"] + "...")
        self.connection_attempt_counts += 1
        self.connection = pika.SelectConnection(parameters=pika.ConnectionParameters(self.config["rabbitmq_host"]),
                                                on_open_callback=on_connected,
                                                on_close_callback=stop_looping_on_close,
                                                on_open_error_callback=on_connection_error
                                                )
        self.start_io_thread()

    def setup_channels(self):
        def on_cmd_channel_open(new_channel):
            """Called when our command channel has opened"""

            def cmd_call_back(frame):
                self.declare_cmd_handles(frame.method.queue)

            self.logger.info("Setting up cmd queue...")
            self.cmd_channel.exchange_declare(exchange='hobbit.command', exchange_type='fanout', auto_delete=True)
            self.cmd_channel.queue_declare(queue='', exclusive=True, callback=cmd_call_back)

        self.cmd_channel = self.connection.channel(on_open_callback=on_cmd_channel_open)

        def on_receiver_channel_open(new_channel):
            """Called when our receiver channel has opened"""
            self.logger.info("Setting up receiving...")

            def rec_train_call_back(frame):
                self.declare_train_data_handler()

            self.receiver_channel.queue_declare(queue=self.config["train_queue_name"], auto_delete=True,
                                                callback=rec_train_call_back)

            def rec_test_call_back(frame):
                self.declare_test_data_handler()

            self.receiver_channel.queue_declare(queue=self.config["task_queue_name"], auto_delete=True,
                                                callback=rec_test_call_back)

        self.receiver_channel = self.connection.channel(on_open_callback=on_receiver_channel_open)

        def on_sender_channel_open(new_channel):
            """Called when our sender channel has opened"""

            def sen_call_back(frame):
                self.declare_data_sender()

            self.logger.info("Setting up sending...")
            self.sender_channel.queue_declare(queue=self.config["answer_queue_name"], auto_delete=True,
                                              callback=sen_call_back)

        self.sender_channel = self.connection.channel(on_open_callback=on_sender_channel_open)

    def declare_cmd_handles(self, command_queue_name):
        # Define handler for commands
        def handle_command(ch, method, properties, body):
            try:
                self.logger.info(f"Received command {body}")
                body_length = len(body)
                if body_length < 4:
                    self.logger.warning("Received faulty message on the command message queue. Ignoring it.")
                    return

                id_length = int.from_bytes(body[:4], byteorder='big', signed=False)
                id_end_pos = id_length + 4
                if body_length < id_end_pos:
                    self.logger.warning(
                        "Got a faulty session id length which exceeds the length of the message received on the "
                        "command queue.")
                    return

                session_id = body[4:id_end_pos].decode("utf-8")
                if session_id != self.session_id:
                    return

                command_id = int.from_bytes(body[id_end_pos:id_end_pos + 1], byteorder='big', signed=False)
                if command_id == TASK_GENERATION_FINISHED_SIGNAL:
                    self.logger.info(f"Received TASK_GENERATION_FINISHED command for session: {session_id}")
                    # We are done
                    self.termination_mutex.release()
                else:
                    self.logger.info(f"Received unknown command: {command_id}")
            except Exception as e:
                self.logger.info(f"Error processing command message: {e}")
            finally:
                ch.basic_ack(delivery_tag=method.delivery_tag)  # Acknowledge message processing

        self.cmd_channel.queue_bind(exchange='hobbit.command', queue=command_queue_name)
        self.cmd_channel.basic_consume(command_queue_name, handle_command)
        logger.info("Command queue communication is set up.")
        self.communication_mutex.release()

    def declare_train_data_handler(self):
        # Define handler for incoming data
        def handle_data(ch, method, header, body):
            self.logger.info("Received data...")
            str_data = body.decode("utf-8")
            thread = Thread(target=self.process_train_data, args=[str_data])
            thread.start()  # TODO this is quite costly. We should use a thread pool instead

        self.receiver_channel.basic_consume(self.config["train_queue_name"], handle_data)
        logger.info("Data receiving communication is set up.")
        self.communication_mutex.release()

    def declare_test_data_handler(self):
        # Define handler for incoming data
        def handle_data(ch, method, header, body):
            self.logger.info("Received data...")
            str_data = body.decode("utf-8")
            thread = Thread(target=self.process_task, args=[str_data])
            thread.start()  # TODO this is quite costly. We should use a thread pool instead

        self.receiver_channel.basic_consume(self.config["task_queue_name"], handle_data)
        logger.info("Data receiving communication is set up.")
        self.communication_mutex.release()

    def declare_data_sender(self):
        logger.info("Data sending communication is set up.")
        self.communication_mutex.release()

    def send_command(self, command_id: int, data: str = None):
        """
        Send a command message to a RabbitMQ exchange for system-level signaling.

        This function constructs and sends a command message to a specified RabbitMQ exchange.
        The command message consists of the session ID and a unique command ID, both encoded into a byte array.

        Args:
            command_id: The unique identifier of the command to be sent.
            data: Additional data that should be added to the command message.

        Returns:
            None

        Raises:
            TypeError: If the `session_id` is not a string or if the `command_id` is not a string or integer.
        """

        try:
            # Define the session_id, command_id, and data as bytes
            content = bytes(len(self.session_id).to_bytes(4, byteorder='big'))
            content += bytes(self.session_id.encode('utf-8'))
            content += bytes([command_id])
            # If there is data to be added to the message
            if (data is not None) and (len(data) > 0):
                content += bytes(data.encode('utf-8'))

            # Publish the message to the specified exchange
            self.cmd_channel.basic_publish(exchange='hobbit.command', routing_key='', body=content)
            self.logger.info(f"Sent {content}")
        except Exception as e:
            self.logger.exception(f"Error sending command: {e}")

    def start_io_thread(self):
        self.io_thread = Thread(target=self.exec_io_loop, args=[])
        self.io_thread.start()

    def exec_io_loop(self):
        # Loop so we can communicate with RabbitMQ
        self.logger.info("Communication thread starting IO loop...")
        self.connection.ioloop.start()

    def run(self):
        try:
            # 1. setup communication
            self.setup_connection()
            self.logger.info("Main thread waiting for the connection to be up...")
            # We have to acquire the lock 3 times
            for x in range(4):
                # Wait for 120 seconds
                if not self.communication_mutex.acquire(timeout=120):
                    raise Exception("Couldn't establish communication within 120 seconds. Aborting.")

            if self.connection is None:
                raise Exception("Couldn't get a connection to RabbitMQ. Aborting.")

            # Send a signal that the system is ready to consume data
            self.logger.info("Setup done. Sending ready signal...")
            self.send_command(SYSTEM_READY_SIGNAL)

            # 4. We are waiting for the message on the command queue that will stop the loop
            self.termination_mutex.acquire()
            self.logger.info("Exiting...")
        except pika.exceptions.AMQPConnectionError as e:
            self.logger.error("Failed to connect to RabbitMQ: %s", e)
            raise e  # throw the exception to show that this container crashed
        except Exception as e:
            logging.exception(f"An error occurred: {e}")
            raise e  # throw the exception to show that this container crashed
        finally:
            try:
                # Try to close the connection
                if self.connection is not None:
                    self.connection.close()
            except Exception as e:
                pass  # nothing to do


def stop_looping_on_close(connection, exception):
    # Invoked when the connection is closed
    if exception is not None:
        logger.error(f"Stopping IOLoop because of: {exception}")
    connection.ioloop.stop()


def main():
    """
    Main function to run the system.

    This function initializes the system, loads a machine learning model,
    processes incoming tasks, and waits for the TASK_GENERATION_FINISHED
    signal before exiting.
    """
    system = SailWinterSchoolBaselineSystem()
    system.run()


if __name__ == "__main__":
    """
    Entry point of the script when executed as the main program.
    """
    main()
