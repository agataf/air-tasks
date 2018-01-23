from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.custom_plugin import MultiTriggerDagRunOperator
from airflow.operators.docker_plugin import DockerWithVariablesOperator

SCHEDULE_DAG_ID = 'chunkedgraph_edgetask_scheduler'
TARGET_DAG_ID = 'chunkedgraph_edgetask_target'

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 1, 1),
    'cactchup_by_default': False,
    'retries': 1,
    'retry_delay': timedelta(seconds=2),
    'retry_exponential_backoff': True,
}

# ####################### SCHEDULER #################################
scheduler_dag = DAG(
    dag_id=SCHEDULE_DAG_ID,
    default_args=default_args,
    schedule_interval=None
)


def param_generator():
    c = {  # Can't move config outside for some reason...
        'dataset': 'pinky40',
        'watershed_path': 'gs://neuroglancer/pinky40_v11/watershed',
        'segmentation_path': \
        'gs://neuroglancer/pinky40_v11/watershed_mst_trimmed_sem_remap',
        'output_path': 'gs://neuroglancer/pinky40_v11/chunked_regiongraph',
        'chunk_size': [512, 512, 64],
        'low_bound': [10240, 7680, 0],
        'high_bound': [65015, 43715, 1002],  # exclusive
        'low_overlap': 0,
        'high_overlap': 1,
    }

    for x in xrange(
            c['low_bound'][0], c['high_bound'][0], c['chunk_size'][0]):
        for y in xrange(
                c['low_bound'][1], c['high_bound'][1], c['chunk_size'][1]):
            for z in xrange(
                    c['low_bound'][2], c['high_bound'][2], c['chunk_size'][2]):
                yield '{} {} {} {}-{}_{}-{}_{}-{}'.format(
                    c['watershed_path'], c['segmentation_path'],
                    c['output_path'],
                    x - c['low_overlap'],
                    x + c['chunk_size'][0] + c['high_overlap'],
                    y - c['low_overlap'],
                    y + c['chunk_size'][1] + c['high_overlap'],
                    z - c['low_overlap'],
                    z + c['chunk_size'][2] + c['high_overlap'])


operator = MultiTriggerDagRunOperator(
    task_id='trigger_%s' % TARGET_DAG_ID,
    trigger_dag_id=TARGET_DAG_ID,
    params_list=param_generator(),
    default_args=default_args,
    dag=scheduler_dag)

# ####################### TARGET DAG #################################

target_dag = DAG(
    dag_id=TARGET_DAG_ID,
    default_args=default_args,
    schedule_interval=None
)

start = DockerWithVariablesOperator(
    ['google-secret.json'],
    mount_point='/secrets',
    task_id='docker_task',
    command='julia /usr/local/chunked-graph/src/tools/edgetask.jl \
             {{ dag_run.conf if dag_run else "" }}',
    default_args=default_args,
    image='nkemnitz/chunked-graph:latest',
    dag=target_dag
)

start.template_fields = start.template_fields + ('command',)
