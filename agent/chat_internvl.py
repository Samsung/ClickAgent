import copy
from utils import encode_image


def init_action_chat():
    operation_history = []
    sysetm_prompt = 'You are a helpful AI mobile phone operating assistant. You need to help me operate the phone to complete the user\'s instruction.'
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': sysetm_prompt}]})
    return operation_history


def init_reflect_chat():
    operation_history = []
    sysetm_prompt = 'You are a helpful AI mobile phone operating assistant.'
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': sysetm_prompt}]})
    return operation_history


def init_process_chat():
    operation_history = []
    sysetm_prompt = 'You are a helpful AI mobile phone operating assistant. You need to help me say what is completed.'
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': sysetm_prompt}]})
    return operation_history


def init_memory_chat():
    operation_history = []
    sysetm_prompt = 'You are a helpful AI mobile phone operating assistant.'
    operation_history.append({'role': 'system', 'content': [{'type': 'text', 'text': sysetm_prompt}]})
    return operation_history


def add_response(role, prompt, chat_history, image=None):
    new_chat_history = copy.deepcopy(chat_history)
    if image:
        base64_image = encode_image(image)
        content = [
            {
                'type': 'text',
                'text': prompt
            },
            {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{base64_image}'
                }
            },
        ]
    else:
        content = [
            {
                'type': 'text',
                'text': prompt
            },
        ]
    new_chat_history.append({'role': role, 'content': content})
    return new_chat_history


def add_response_two_image(role, prompt, chat_history, image):
    new_chat_history = copy.deepcopy(chat_history)

    base64_image1 = encode_image(image[0])
    base64_image2 = encode_image(image[1])
    content = [
        {
            'type': 'text',
            'text': prompt
        },
        {
            'type': 'image_url',
            'image_url': {
                'url': f'data:image/jpeg;base64,{base64_image1}'
            }
        },
        {
            'type': 'image_url',
            'image_url': {
                'url': f'data:image/jpeg;base64,{base64_image2}'
            }
        },
    ]

    new_chat_history.append({'role': role, 'content': content})
    return new_chat_history


def print_status(chat_history):
    print('*' * 100)
    for chat in chat_history:
        print('role:', chat[0])
        print(chat[1][0]['text'] + '<image>' * (len(chat[1]) - 1) + '\n')
    print('*' * 100)


def init_eval_chat():
    operation_history = {'role': 'system', 'content': [{'type': 'text', 'text': """You are an expert in evaluating the performance of an android navigation agent. The agent is designed to help a human user navigate the device to complete a task. Given the user's intent, action history, and the state of the screen, your goal is to decide whether the agent has successfully completed the task or not. 
If user cannot complete task, beacuse for example: some product is out of stock. It is success. Select means click, so user has to click to select something. User do not want to click anything, so your purpose is to decide if actual screen shows the final state of the instruction.

*IMPORTANT*
Format your response into two lines as shown below:

Thoughts: <your thoughts and reasoning process based>
Status: "success" or "failure"
Rate: 1-10 <scale in 1-10 how much convinced are you>
"""}]}

    return operation_history
