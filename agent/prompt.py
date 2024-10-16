def get_action_prompt(instruction, keyboard, summary_history, action_history, thought_history, add_info,
                      completed_content, memory, do_stop, option, use_open_app):
    print("Using open app module: ", use_open_app)
    prompt = f"This image is a phone screenshot. The user's instruction is: {instruction}.\n\n"
    if add_info:
        prompt += "### Hint ###\n"
        prompt += "Hints to help you complete the user's instructions are as follows:\n"
        prompt += add_info
        prompt += "\n\n"

    if completed_content:
        prompt += "### Progress ###\n"
        prompt += "Completed contents:\n" + completed_content + "\n\n"

    if action_history:
        prompt += "### History Operations ###\n"
        prompt += "Refer to the completed operations to decide the next operation. These operations are as follows:\n"
        for i in range(len(action_history)):
            prompt += f"Step-{i + 1}: [Thought: {thought_history[i]};Operation: {summary_history[i].split(' to ')[0].strip()};]\n"
        prompt += "\n"

    if memory:
        prompt += "### Memory ###\n"
        prompt += "Recorded contents for use in subsequent operations:\n"
        prompt += "Memory:\n" + memory + "\n"

    # if error_flag:
    #     prompt += "### Last Operation ###\n"
    #     prompt += f"Previous operation \"{last_summary}\" with Action \"{last_action}\" did not meet expectations. Reflect and revise your operation this time.\n\n"

    prompt += "### Response Requirements ###\n"
    prompt += "You must choose one of the following actions on the current page:\n"
    if keyboard:
        prompt += '''
            1. Type (\"typed text\"). Please generate it only with (\"typed text\") nothing else. 
        '''
    elif option == 1:
        if use_open_app:
            prompt += "1. Go To App - <name of the app>. Use this command if you want to open app on the phone. Do not search for any app, just use this command. Generate it with name of the app in given format so after ' - '. For example: 'Go To App - Google Chrome'."
        else:
            prompt += '''
    1. Click (brief description). Use this command if you want to click somewhere. Please generate it with a brief description of the icon in natural language. You can also click on search boxes, address bars and search bars, if you want start typing, but specify which input should be clicked. Address bar and search bar is not the same thing.
    2. Swipe up-to-bottom/bottom-to-up/left-to-right/right-to-left. Use these commands to drag a page, for example, from top-to-bottom. Choose from 4 options.
    3. Home. Exit the app and go back to the desktop.
        '''
    elif option == 2:
        prompt += '''
    1. Click (brief description). Use this command if you want to click somewhere. Please generate it with a brief description of the icon in natural language.
    2. Swipe up-to-bottom/bottom-to-up/left-to-right/right-to-left. Use these commands to drag a page, for example, from top-to-bottom. Choose from 4 options.
    3. Home. Exit the app and go back to the desktop.
    4. Type (\"typed text\"). Use this command if you want to click search box/bar/icon or other UI element to type some text. Please generate it only with (\"typed text\") nothing else.
        '''
        if use_open_app:
            prompt += "1. Go To App - <name of the app>. Use this command if you want to open 3rd party app on the phone. It is the best way to open this app or check if there is app existing on phone. Generate it with name of the app in given format so after ' - '. For example: 'Go To App - Instagram'."

    prompt += "5. STOP. If user command is properly performed, then choose this action" if do_stop else ''
    prompt += "\n### Output Format ###\n"
    prompt += "Your output must follow this format on the same line and consists of the following six parts:\n"
    prompt += "Thought: Think about the requirements that have been completed in previous operations and the requirements that need to be completed in the next one operation.\n"
    prompt += "Action: You can only use one action from the above actions, based on your thought. Change (brief description) to description based on your thought.\n"
    prompt += "Operation: Please generate a brief natural language description for the operation in Action based on your Thought.\n"
    prompt += "Command: Please generate a brief natural language description of your Operation. Make it short natural language command.\n"
    prompt += "Description: Please generate a brief description of UI element you want to click based on your thought, operation and screenshot information. If you want to open app you can add to description it's name for example \'Chrome\', \'Google Play\', etc. If you want to click on search bar/box/address bar etc. you can add placeholder. Please do not use oridinal numbers, like 'first', 'second' etc.. For example instead of returning: 'The first entry is the \"Leaf blowers\" priced at $82.00.' return '\"Leaf blowers\" priced at $82.00.', instead of 'The first listing is the \"Power Tools\" priced at 9.15 SEK.' ==> 'The \"Power Tools\" priced at 9.15 SEK.'. Be more specific with description.\n"
    prompt += "Ground truth: Please generate a text if you click on search box/bar/address bar etc. which should be written there. Only return text. Make step by step typing.\n"
    prompt += "(Use English for the output, return these six parts, return output in the same lines)\n"

    return prompt


def get_action_prompt_with_analysis(instruction, keyboard, summary_history, action_history, thought_history,
                                    analysis_history, add_info, completed_content, memory, do_stop, option,
                                    use_open_app):
    prompt = "### Background ###\n"
    prompt += f"This image is a phone screenshot. The user's end goal instruction is: {instruction}. Analyze this instruction step by step, think about where to do this task and what is the exact goal.\n\n"
    prompt += f"Your responsibility is to do steps in a way that you will achieve this goal which can be reaching some point in phone only or doing exact task or search for answear to question.\n\n"

    if add_info:
        prompt += "### Hint ###\n"
        prompt += "Hints to help you complete the user's instructions are as follows:\n"
        prompt += add_info
        prompt += "\n\n"

    prompt += "### Must follow rules ###\n"
    prompt += "You are always responsible for searching for items to click. Always be specific about what to click at. Never trigger click action if you do not see element on screen.\n"
    prompt += "Focus on purpose of task, analyse it step by step. When question is about some information extraction, then return data that is answering question in 'answer' when successfull.\n"
    prompt += "If you are given to do task in app, then look for it in phone, those can be installed. Never look for apps on google.\n"
    prompt += "You have to do exactly what is told to you. If instruction says to do some actions in specific app then you must do this in this specific app. Never do things in other way.\n"

    if len(action_history) > 0:
        prompt += "### History Operations ###\n"
        prompt += "Refer to thoughts of agent doing those operations and tasks that agent was given for each step. Remember that agent could do those tasks wrong, so it is not sure that those tasks were done correctly. Refer to analysis part to check if those tasks were done correctly:\n"
        for i in range(len(action_history)):
            prompt += f"Step-{i + 1}: [Thought: {thought_history[i]};Operation: {summary_history[i].split(' to ')[0].strip()}]\n"
        prompt += "\n"

    if analysis_history:
        prompt += "### Given agent operations analysis history ###\n"
        prompt += "Refer to the analysis of operations done by agent. These operations are as follows:\n"
        for i in range(len(analysis_history)):
            prompt += f"Step-{i + 1}: [Analysis of operation done by agent: {analysis_history[i].strip()}\n"
        prompt += "\n"

    prompt += "### Must follow rules ###\n"
    prompt += "You are always responsible for searching for items to click. Always be specific about what to click at. Never trigger click action if you do not see element on screen.\n"
    prompt += "Focus on purpose of task, analyse it step by step. When question is about some information extraction, then return data that is answering question in 'answer' when successfull.\n"
    prompt += "If you are given to do task in app, then look for it in phone, those can be installed. Never look for apps on google.\n"
    prompt += "You have to do exactly what is told to you. If instruction says to do some actions in specific app then you must do this in this specific app. Never do things in other way.\n"

    prompt += "### Response Requirements ###\n"
    prompt += "You must choose one of the following actions on the current page:\n"
    if keyboard:
        prompt += '''
            1. Type (\"typed text\"). Please generate it only with (\"typed text\") nothing else. 
        '''
    # OPEN APP MODULE - TO ADD
    #    3. Go To App - <name of the app>. Use this command if you want to open 3rd party app on the phone. It is the best way to open this app or check if there is app existing on phone. Generate it with name of the app in given format so after ' - '. For example: 'Go To App - Instagram'.
    elif option == 1:
        prompt += '''
        1. Click (brief description). Use this command if you want to click somewhere. Please generate it with a brief description of the icon in natural language. You can also click on search boxes, address bars and search bars, if you want start typing, but specify which input should be clicked. Address bar and search bar is not the same thing.
        2. Swipe up-to-bottom/bottom-to-up/left-to-right/right-to-left. Choose from 4 options.
            - Use these commands to drag a page, for example, from up-to-bottom means that you take cursor (touch) from top part of screen to bottom part of screen. 
            - Use command left-to-right to go one step back if something went wrong. Left-to-right must start from exactly start of left side of screen when considering coordinates.        
        3. Home. Exit the app and go back to the desktop.
        '''
        if use_open_app:
            prompt += "4. Go To App - <name of the app>. Use this command if you want to open 3rd party app on the phone. It is the best way to open this app or check if there is app existing on phone. Generate it with name of the app in given format so after ' - '. For example: 'Go To App - Instagram'."

    elif option == 2:
        prompt += '''
        1. Click (brief description). Use this command if you want to click somewhere. Please generate it with a brief description of the icon in natural language.
        2. Swipe up-to-bottom/bottom-to-up/left-to-right/right-to-left. Choose from 4 options.
            - Use these commands to drag a page, for example, from up-to-bottom means that you take cursor (touch) from top part of screen to bottom part of screen. 
            - Use command left-to-right to go one step back if something went wrong. Left-to-right must start from exactly start of left side of screen when considering coordinates.        
        3. Home. Exit the app and go back to the desktop.
        4. Type (\"typed text\"). Use this command if you want to click search box/bar/icon or other UI element to type some text. Please generate it only with (\"typed text\") nothing else.
        '''
        if use_open_app:
            prompt += "5. Go To App - <name of the app>. Use this command if you want to open 3rd party app on the phone. It is the best way to open this app or check if there is app existing on phone. Generate it with name of the app in given format so after ' - '. For example: 'Go To App - Instagram'."

    prompt += "5. STOP. If user command is properly performed, then choose this action" if do_stop else ''

    prompt += "\n### Output Format ###\n"
    prompt += "Your output must follow this format on the same line and consists of the following seven parts:\n"
    prompt += "Thought: Think about the requirements that have been completed in previous operations and the requirements that need to be completed in the next one operation.\n"
    prompt += "Action: You can only use one action from the above actions, based on your thought. Change (brief description) to description based on your thought.\n"
    prompt += "Operation: Please generate a brief natural language description for the operation in Action based on your Thought.\n"
    prompt += "Command: Please generate a brief natural language description of your Operation. Make it short natural language command.\n"
    prompt += "Description: Please generate a brief description of UI element you want to click based on your thought, operation and screenshot information. You can add to description it's name for example \'Chrome\', \'Google Play\', etc. Please do not use oridinal numbers, like 'first', 'second' etc.. For example instead of returning: 'The first entry is the \"Element you mention about\".' return '\"Element you mention about\".', instead of 'The first listing is the \"Element you mention about\"' ==> 'The \"Element you mention about\".'.\n"
    prompt += "Ground truth: Please generate a text if you click on search box/bar/address bar etc. which should be written there. Only return text.\n"
    prompt += "(Use English for the output, return these seven parts, return output in the same lines, you must return same seven keys with their values)\n"

    return prompt


def get_relevant_app_prompt(app_name, apps_label):
    prompt = f'''Return app that is relevant from app list that is the nearest to the search app

search app: {app_name}

app list:
{apps_label}

Return answer in given format below:

app: <return exact name of the app from app list that is relevant to search app>
        '''
    return prompt


def get_analysis_prompt(instruction, action, analysis_history):
    prompt = (
        "You are provided with two phone screenshots: one taken before the operation and one taken after. Additionally, you have:\n"
        "- A global instruction for the entire operation.\n"
        "- A specific task to complete between the two screenshots.\n"
        "- An analysis history of previous steps.\n\n"
        "Your job is to carefully analyze the two screenshots and determine if any progress has been made according to the global instruction and the specific task.\n\n"
        "Focus on the following:\n\n"
        "1. **Task Progress**: Does the difference between the two screenshots indicate that the current task has been completed? Has the correct element been interacted with or clicked, based on the instructions?\n"
        "2. **Correctness**: Was the correct task performed? If the task was misinterpreted (e.g., the global instruction was to open Instagram, but the agent opened Notes), highlight that error.\n"
        "3. **Global Instruction Alignment**: Are the changes in line with the global instruction, even if the task itself isn't fully complete?\n\n"
        "### Analysis History ###\n"
    )

    for i, analysis in enumerate(analysis_history, 1):
        prompt += f"Step-{i}: [Analysis of given step: {analysis.strip()}]\n\n"

    prompt += (
        "### Current Operation ###\n"
        f"- **Global Instruction**: {instruction}\n"
        f"- **Current Task**: {action}\n\n"
        "### Output Format ###\n"
        "Your analysis should be presented in the following format:\n\n"
        "Analysis: Write 'Done Correctly' or 'Done Incorrectly' which tells if current task was done correctly or not and after that, splitted using this symbol ' - ' generate a brief natural language analysis of situation. Consider the task, global instruction, and previous steps when explaining. Make sure to explain any errors or deviations in the operation. "
        "**Note**: Your analysis should focus on the correctness of the **current task**, not whether the entire global instruction is completed."
    )
    return prompt


def get_reflect_prompt(instruction, clickable_infos1, clickable_infos2, width, height, keyboard1, keyboard2, summary,
                       action, add_info):
    prompt = f"These images are two phone screenshots before and after an operation. Their widths are {width} pixels and their heights are {height} pixels.\n\n"

    # prompt += "### Before the current operation ###\n"
    # prompt += "Screenshot information:\n"
    # for clickable_info in clickable_infos1:
    #     if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
    #         prompt += f"[{{}}, {{}}]; {{}}\n".format(clickable_info['coordinates'][0], clickable_info['coordinates'][1], clickable_info['text'])

    # prompt += "### After the current operation ###\n"
    # prompt += "Screenshot information:\n"
    # for clickable_info in clickable_infos2:
    #     if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
    #         prompt += f"[{{}}, {{}}]; {{}}\n".format(clickable_info['coordinates'][0], clickable_info['coordinates'][1], clickable_info['text'])

    prompt += "### Current operation ###\n"
    prompt += f"The user's instruction is: {instruction}. In the process of completing the requirements of the instruction, an operation is performed on the phone. Below are the details of this operation:\n"
    prompt += "Operation thought: " + summary.split(" to ")[0].strip() + "\n"
    prompt += "Operation action: " + action
    prompt += "\n\n"

    prompt += "### Response requirements ###\n"
    prompt += "Now you need to output the following content based on the screenshots before and after the current operation:\n"
    prompt += "Whether the result of the \"Operation action\" meets your expectation of \"Operation thought\"?\n"
    prompt += "A: The result of the \"Operation action\" meets my expectation of \"Operation thought\".\n"
    prompt += "B: The \"Operation action\" results in a wrong page and I need to return to the previous page.\n"
    prompt += "C: The \"Operation action\" produces no changes."
    prompt += "\n\n"

    prompt += "### Output format ###\n"
    prompt += "Your output format is:\n"
    prompt += "Thought: [Your thought about the question]\n"
    prompt += "Action: [A or B or C]"

    return prompt


def get_memory_prompt(insight):
    if insight != "":
        prompt = "### Important content ###\n"
        prompt += " ".join(insight)
        prompt += "\n\n"

        prompt += "### Response requirements ###\n"
        prompt += "Please think about whether there is any content closely related to ### Important content ### on the current page? If there is, please output the content. If not, please output \"None\".\n\n"

    else:
        prompt = "### Response requirements ###\n"
        prompt += "Please think about whether there is any content closely related to user\'s instrcution on the current page? If there is, please output the content. If not, please output \"None\".\n\n"

    prompt += "### Output format ###\n"
    prompt += "Your output format is:\n"
    prompt += "Important content: The content or None. Please do not repeatedly output the information in ### Memory ###."

    return prompt


def get_process_prompt(instruction, thought_history, summary_history, action_history, completed_content, add_info):
    prompt = "### Background ###\n"
    prompt += f"There is an user's instruction which is: {instruction}. You are a mobile phone operating assistant and are operating the user's mobile phone.\n\n"

    if add_info != "":
        prompt += "### Hint ###\n"
        prompt += "There are hints to help you complete the user's instructions. The hints are as follow:\n"
        prompt += add_info
        prompt += "\n\n"

    if len(thought_history) > 1:
        prompt += "### History operations ###\n"
        prompt += "To complete the requirements of user's instruction, you have performed a series of operations. These operations are as follow:\n"
        for i in range(len(summary_history)):
            operation = summary_history[i].split(" to ")[0].strip()
            prompt += f"Step-{i + 1}: [Operation thought: " + operation + "; Operation action: " + action_history[
                i] + "]\n"
        prompt += "\n"

        prompt += "### Progress thinking ###\n"
        prompt += "After completing the history operations, you have the following thoughts about the progress of user's instruction completion:\n"
        prompt += "Completed contents:\n" + completed_content + "\n\n"

        prompt += "### Response requirements ###\n"
        prompt += "Now you need to update the \"Completed contents\". Completed contents is a general summary of the current contents that have been completed based on the ### History operations ###.\n\n"

        prompt += "### Output format ###\n"
        prompt += "Your output format is:\n"
        prompt += "Completed contents:\nUpdated Completed contents. Don't output the purpose of any operation. Just summarize the contents that have been actually completed in the ### History operations ###."

    else:
        prompt += "### Current operation ###\n"
        prompt += "To complete the requirements of user's instruction, you have performed an operation. Your operation thought and action of this operation are as follows:\n"
        prompt += f"Operation thought: {thought_history[-1]}\n"
        operation = summary_history[-1].split(" to ")[0].strip()
        prompt += f"Operation action: {operation}\n\n"

        prompt += "### Response requirements ###\n"
        prompt += "Now you need to combine all of the above to generate the \"Completed contents\".\n"
        prompt += "Completed contents is a general summary of the current contents that have been completed. You need to first focus on the requirements of user's instruction, and then summarize the contents that have been completed.\n\n"

        prompt += "### Output format ###\n"
        prompt += "Your output format is:\n"
        prompt += "Completed contents: Generated Completed contents. Don't output the purpose of any operation. Just summarize the contents that have been actually completed in the ### Current operation ###. Look on the current screenshot if operation was not properly executed, do not take this operation as completed.\n"
        prompt += "(Please use English to output)"

    return prompt


def get_click_prompt(app_name: str):
    prompt = f"Please provide the coordinates (x, y) of the {app_name} application on the screen. Return only the coordinates as numbers, nothing else."
    return prompt


def build_final_eval_v3_final_prompt_web(
        intent, last_actions
):
    prompt = f"""
All requirements of user intent has to be done to mark action as success. The action history is also important. On the web shopping pages may not be some products then it is also a success, as other products will be displayed and another will be selected.
User Intent: {intent}
Remember whole intent has to be done to mark as success. If user intent is question, you have to be able to answer it based on screen caption.
Action History:
{last_actions}
"""
    return prompt


def build_final_eval_v3_final_prompt_general(
        intent, last_actions
):
    prompt = f"""
All requirements of user intent has to be done to mark action as success. Based on actual screen caption you have to decide if user intent is done.
User Intent: {intent}
Action History:
{last_actions}
"""
    return prompt


def build_init_eval_general():
    return """You are an expert in evaluating the performance of an android navigation agent. The agent is designed to help a human user navigate the device to complete a task. Given the user's intent, action history, and the state of the screen, your goal is to decide whether the agent has successfully completed the task or not. 
If user cannot complete task, beacuse for example: some product is out of stock. It is success. Select means click, so user has to click to select something.
*IMPORTANT*
Format your response into two lines as shown below:
Thoughts: <your thoughts and reasoning process based>
Answer: <Answer user intent based on screen caption, if you cannot return N/A.>
Status: "success" or "failure"
Rate: 1-10 <scale in 1-10 how much convinced are you>
"""


def build_init_eval_web():
    return """You are an expert in evaluating the performance of an android navigation agent. The agent is designed to help a human user navigate the device to complete a task. Given the user's intent, action history, and the state of the screen, your goal is to decide whether the agent has successfully completed the task or not. 
If user cannot complete task, beacuse for example: some product is out of stock. It is success. Select means click, so user has to click to select something. User do not want to click anything, so your purpose is to decide if actual screen shows the final state of the instruction.

*IMPORTANT*
Format your response into two lines as shown below:

Thoughts: <your thoughts and reasoning process based>
Status: "success" or "failure"
Rate: 1-10 <scale in 1-10 how much convinced are you>
"""
