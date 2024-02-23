import sys
import logging
import os
import signal
import pika
import pandas as pd
import time
from rdflib import Graph, URIRef  # Used to access the RDF meta data of the system instance
from threading import Thread
import numpy as np
import io
import math

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the predefined command IDs
BENCHMARK_READY_SIGNAL = 2
TASK_GENERATOR_START_SIGNAL = 8
BENCHMARK_FINISHED_SIGNAL = 11
TASK_GENERATION_FINISHED_SIGNAL = 15
START_BENCHMARK_SIGNAL = 17
LEARNING_FINISHED_SIGNAL = 101

MAX_CONNECTION_ATTEMPTS = 5
SECONDS_BETWEEN_CONNECTION_ATTEMPTS = 5

BENCHMARK_NAMESPACE = "http://example.org/sail-winter-school-2024/benchmark/"
# Specify the folder path containing your CSV files within the Docker container
DATA_FOLDER_PATH = '/data/'
FILE_CSV_SEPARATOR = ';'
MESSAGE_CSV_SEPARATOR = ';'
TRAIN_DATA_AMOUNT = 0.9


class BenchmarkResult:

    def __init__(self, kpi_iri: str, value: str, data_type: str = None):
        self.kpi_iri = kpi_iri
        self.data_type = data_type
        self.value = value


class SailWinterSchoolBenchmark:

    def __init__(self):
        self.session_id = os.getenv("HOBBIT_SESSION_ID")
        self.config = {
            "rabbitmq_host": os.getenv("HOBBIT_RABBIT_HOST", "127.0.0.1"),
            "session_id": os.getenv("HOBBIT_SESSION_ID", ""),
            "experiment_uri": os.getenv("HOBBIT_EXPERIMENT_URI", ""),
            "benchmark_parameter_model": os.getenv("BENCHMARK_PARAMETERS_MODEL", ""),
            #    "rabbitmq_user": os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
            #    "rabbitmq_pass": os.getenv("RABBITMQ_DEFAULT_PASS", "guest"),
            "train_queue_name": "hobbit.datagen-system." + self.session_id,
            "task_queue_name": "hobbit.taskgen-system." + self.session_id,
            "answer_queue_name": "hobbit.system-evalstore." + self.session_id,
        }
        # Parse the parameter model and get parameter values
        self.parameters_graph = Graph()
        self.parameters_graph.parse(data=self.config["benchmark_parameter_model"], format="json-ld")
        self.dataset_iri = self.parameters_graph.objects(predicate=URIRef(BENCHMARK_NAMESPACE + "dataset")).__next__()
        if self.dataset_iri is None:
            logger.error(f"Dataset IRI parameter is not set.")
            raise AttributeError()
        seed_str = self.parameters_graph.objects(predicate=URIRef(BENCHMARK_NAMESPACE + "seed")).__next__()
        if seed_str is None:
            logger.error(f"Seed parameter is not set.")
            raise AttributeError()
        self.seed = int(seed_str)

        self.connection = None
        self.connection_attempt_counts = 0
        self.channel = None
        self.next_task_id = 0
        self.system_id = None
        self.test_data = None
        self.train_data = None
        self.timestamps_sent = {}
        self.timestamps_received = {}
        self.answers = {}

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
        # Init RNG
        rng = np.random.default_rng(seed=self.seed)
        # Split data into train and test data
        is_train_data = rng.random(size=len(data)) < TRAIN_DATA_AMOUNT
        self.train_data = data[is_train_data]
        self.test_data = data[~is_train_data]
        # Let them drop indexes; we can use the index of the test data later on as task ID
        self.train_data.reset_index(drop=True, inplace=True)
        self.test_data.reset_index(drop=True, inplace=True)

    def send_train_data(self):
        logger.info("Sending training data...")
        train_csv = self.train_data.to_csv(sep=MESSAGE_CSV_SEPARATOR)
        self.channel.basic_publish(exchange='', routing_key=self.config["train_queue_name"], body=train_csv)

    def run_evaluation(self):
        self.send_command(TASK_GENERATION_FINISHED_SIGNAL)
        logger.info("Starting evaluation...")
        self.evaluate()
        logger.info("Everything is done.")
        self.connection.ioloop.stop()

    def send_task(self):
        """
        Sends a task to the task queue.
        """
        task_queue = self.config["task_queue_name"]
        task_csv = self.test_data.iloc[[self.next_task_id]].to_csv(sep=MESSAGE_CSV_SEPARATOR, header=True)
        self.channel.basic_publish(exchange='', routing_key=task_queue, body=task_csv)
        # Add the time stamp at which we sent the data
        self.timestamps_sent[self.next_task_id] = time.time_ns()
        logger.info(f"Sent task #{self.next_task_id} at {self.timestamps_sent[self.next_task_id]}")
        self.next_task_id += 1

    def evaluate(self):
        """
        """
        # Iterate over all single tasks and gather statistics as needed
        expected_result_column = len(self.test_data.columns) - 1
        error_count = 0
        runtimes = []
        for i in range(len(self.test_data)):
            answer_data = self.answers[i]
            received_at = self.timestamps_received[i]
            if answer_data is not None and received_at is not None:
                # Compare answer_data with the expected answer
                # expected answer: test_data.iloc[i, expected_result_column]
                # prediction of the system: answer_data.iloc[0, 1]

                runtimes.append((received_at - self.timestamps_sent[i]) / 1000.0)
            else:
                ++error_count

        # Determine the KPIs we are interested in
        results = []
        # Here, it would be good to measure some quality...

        # Average runtime and its standard deviation
        runtime_avg = float('nan')
        runtime_std_dev = float('nan')
        logger.info(f"timestamps: {runtimes}")
        if len(runtimes) > 0:
            runtime_avg = sum(runtimes) / len(runtimes)
            runtime_std_dev = math.sqrt(sum([(x - runtime_avg) ** 2 for x in runtimes]) / len(runtimes))
        results.append(BenchmarkResult(kpi_iri=BENCHMARK_NAMESPACE+"avgRuntime",
                                       value=runtime_avg, data_type="xsd:double"))
        results.append(BenchmarkResult(kpi_iri=BENCHMARK_NAMESPACE + "stdDevRuntime",
                                       value=runtime_std_dev, data_type="xsd:double"))
        # Number of test data instances and number of faulty answers
        results.append(BenchmarkResult(kpi_iri=BENCHMARK_NAMESPACE+"testDataSize",
                                       value=len(self.test_data), data_type="xsd:long"))
        results.append(BenchmarkResult(kpi_iri=BENCHMARK_NAMESPACE+"faultyResponses",
                                       value=error_count, data_type="xsd:long"))

        # Send an RDF model with the results to the platform
        self.send_result(results)

    # ************************************************************************************************************
    # *** From here on, the implementation focuses on the setup of the communication and the general workflow. ***
    # *** It might not be too interesting for the beginning.                                                   ***
    # ************************************************************************************************************

    def send_result(self, results):
        """
        """
        logger.info("Sending result...")
        # Write context
        result_model = ("{\"@context\": {\"hobbit\": \"http://w3id.org/hobbit/vocab#\","
                        "\"xsd\": \"http://www.w3.org/2001/XMLSchema#\"")
        for i in range(len(results)):
            result_model += f",\"kpi{i}\": " + "{\"@id\": \"" + results[i].kpi_iri +  "\","
            if results[i].data_type is not None :
                result_model += "\"@type\": \""+ results[i].data_type + "\""
            result_model += "}"
        # Write experiment information
        result_model += "},\"@id\": \"" + self.config["experiment_uri"] + "\",\"@type\": \"hobbit:Experiment\""
        # Write KPI values
        for i in range(len(results)):
            result_model += f",\"kpi{i}\": \"{results[i].value}\""
        result_model += "}"

        logger.info("Sending result model: " + result_model)
        self.send_command(BENCHMARK_FINISHED_SIGNAL, result_model)
        # It seems like we shouldn't quit too fast. Otherwise, the platform may think that the benchmark crashed.
        # Let's wait for 20 seconds...
        time.sleep(20)

    def send_next_task(self):
        if self.next_task_id < len(self.test_data):
            logger.info(f"Sending task # {self.next_task_id}...")
            # TODO This is costly. We should use a thread pool.
            thread = Thread(target=self.send_task, args=[])
            thread.start()
            # self.send_task()
        else:
            logger.info("All tasks generated.")
            # TODO This is costly. We should use a thread pool.
            thread = Thread(target=self.run_evaluation, args=[])
            thread.start()

    def send_command(self, command_id, data=None):
        """
        Sends a command to the command queue.

        Args:
            command_id: The command ID to be sent.
            data: Additional data for the command (optional).
        """
        try:
            # Define the session_id, command_id, and data as bytes
            content = bytes(len(self.session_id).to_bytes(4, byteorder='big'))
            content += bytes(self.session_id.encode('utf-8'))
            content += bytes([command_id])
            if data is not None:
                content += data.encode('utf-8')

            # Publish the message to the specified exchange
            self.channel.basic_publish(exchange='hobbit.command', routing_key='', body=content)
            logger.info(f"Sent {content}")
        except Exception as e:
            logger.exception(f"Error sending command: {e}")

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
            logger.info("Got a new connection.")
            self.connection = new_connection
            # self.connection_mutex.release()
            self.setup_channel()

        def on_connection_error(new_connection, exception):
            """Called when we are fully connected to RabbitMQ"""
            if self.connection_attempt_counts < MAX_CONNECTION_ATTEMPTS:
                logger.info("Got an error while waiting for the connection. Trying it again...")
                time.sleep(SECONDS_BETWEEN_CONNECTION_ATTEMPTS)
                self.connection = pika.SelectConnection(
                    parameters=pika.ConnectionParameters(self.config["rabbitmq_host"]),
                    on_open_callback=on_connected,
                    on_close_callback=stop_looping_on_close,
                    on_open_error_callback=on_connection_error
                )
            else:
                logger.exception(exception)
                # self.connection_mutex.release()

        # Get the mutex to make the thread wait for the connection later on
        # self.connection_mutex.acquire()
        logger.info("Trying to connect to " + self.config["rabbitmq_host"] + "...")
        self.connection_attempt_counts += 1
        self.connection = pika.SelectConnection(parameters=pika.ConnectionParameters(self.config["rabbitmq_host"]),
                                                on_open_callback=on_connected,
                                                on_close_callback=stop_looping_on_close,
                                                on_open_error_callback=on_connection_error
                                                )

    def setup_channel(self):
        def on_channel_open(new_channel):
            """Called when our channel has opened"""
            logger.info("Got a new channel.")
            self.channel = new_channel
            self.declare_queues_step1()

        self.connection.channel(on_open_callback=on_channel_open)

    def declare_queues_step1(self):
        """
        Initialize the system by declaring and binding exchanges and queues.
        """
        logger.info("Setting up queues...")

        def call_step2(frame):
            self.declare_queues_step2(frame.method.queue)

        # Declare and bind the exchange and queue for the command queue
        self.channel.exchange_declare(exchange='hobbit.command', exchange_type='fanout', auto_delete=True)
        self.channel.queue_declare(queue='', exclusive=True, callback=call_step2)

    def declare_queues_step2(self, command_queue_name):
        # Define handler for commands
        def handle_command(ch, method, properties, body):
            try:
                logger.info(f"Received command {body}")
                body_length = len(body)
                if body_length < 4:
                    logger.warning("Received faulty message on the command message queue. Ignoring it.")
                    return

                id_length = int.from_bytes(body[:4], byteorder='big', signed=False)
                id_end_pos = id_length + 4
                if body_length < id_end_pos:
                    logger.warning(
                        "Got a faulty session id length which exceeds the length of the message received on the "
                        "command queue.")
                    return

                session_id = body[4:id_end_pos].decode("utf-8")
                if session_id != self.session_id:
                    logger.info(f"{session_id} != {self.session_id}")
                    return

                command_id = int.from_bytes(body[id_end_pos:id_end_pos + 1], byteorder='big', signed=False)
                if command_id == START_BENCHMARK_SIGNAL:
                    logger.info(f"Received START_BENCHMARK_SIGNAL command for session: {session_id}")
                    self.system_id = body[id_end_pos + 1:].decode("utf-8")
                    # We should start the benchmarking process by sending the first task
                    self.send_train_data()
                elif command_id == LEARNING_FINISHED_SIGNAL:
                    # The system is trained. We should send the first task
                    self.send_next_task()
                else:
                    print(f"Received unknown command: {command_id}")
            except Exception as e:
                print(f"Error processing command message: {e}")
            finally:
                ch.basic_ack(delivery_tag=method.delivery_tag)  # Acknowledge message processing

        self.channel.queue_bind(exchange='hobbit.command', queue=command_queue_name)
        self.channel.basic_consume(command_queue_name, handle_command)

        def call_step3(frame):
            self.declare_queues_step3()

        # Declare task queue
        self.channel.queue_declare(queue=self.config["task_queue_name"], auto_delete=True, callback=call_step3)

    def declare_queues_step3(self):
        def call_step4(frame):
            self.declare_queues_step4()

        # Declare queue for incoming data and add handler to consume data
        self.channel.queue_declare(queue=self.config["answer_queue_name"], auto_delete=True, callback=call_step4)

    def declare_queues_step4(self):
        # Define handler for incoming data
        def handle_data(ch, method, header, body):
            # First, get the current time
            timestamp_received = time.time_ns()
            # Try to parse the answer
            try:
                # Parse the answer as CSV
                str_data = body.decode("utf-8")
                response_data = pd.read_csv(io.StringIO(str_data), sep=MESSAGE_CSV_SEPARATOR, header=None)
                # The first element should be the task ID
                task_id = response_data.iloc[0, 0]
                self.answers[task_id] = task_id
                self.timestamps_received[task_id] = timestamp_received
                logger.info(f"Received an answer for #{task_id} at {timestamp_received}...")
            except Exception as e:
                logging.exception(f"An error occurred while parsing answer: {e}")
            # Send next task
            self.send_next_task()

        self.channel.basic_consume(self.config["answer_queue_name"], handle_data)

        def call_step5(frame):
            self.declare_queues_step5()

        # Declare data queue
        self.channel.queue_declare(queue=self.config["train_queue_name"], auto_delete=True, callback=call_step5)

    def declare_queues_step5(self):
        # Send a signal that the benchmark is ready to start
        logger.info("Setup done. Sending ready signal...")
        self.send_command(BENCHMARK_READY_SIGNAL)

    def run(self):
        try:
            self.prepare_data()
            self.setup_connection()
            logger.info("Main thread waiting for the connection to be up...")
            if self.connection is None:
                logger.error("Didn't get a connection. Aborting!")
                return
            # Loop so we can communicate with RabbitMQ
            logger.info("Main thread starting IO loop...")
            self.connection.ioloop.start()
            # We are waiting for the message on the command queue that will stop the loop
            logger.info("Exiting...")
            self.connection = None
        except pika.exceptions.AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
        except Exception as e:
            logging.exception(f"An error occurred: {e}")
        finally:
            try:
                # Try to close the connection
                if self.connection is not None:
                    self.connection.close()
            except Exception as e:
                pass  # nothing to do


def stop_looping_on_close(connection, exception):
    # Invoked when the connection is closed
    connection.ioloop.stop()


def main():
    """
    Main function to run the system.

    This function initializes the system, loads a machine learning model,
    processes incoming tasks, and waits for the TASK_GENERATION_FINISHED
    signal before exiting.
    """
    benchmark = SailWinterSchoolBenchmark()
    benchmark.run()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0))
    main()
