Seven principles have been identified as being important for the design and evaluation of interactive systems, one of which is “Suitability for the user’s tasks”.
— Suitability for the user’s tasks: An interactive system is suitable for the user's tasks when it supports the users in the completion of their tasks, i.e. when the operating functions and the user-system interactions are based on the task characteristics (rather than the technology chosen to perform the task).
For the principle, this document provides a list of general design recommendations. The application of a single recommendation does not mean that the application of a principle has been fully satisfied.
While the principle and general design recommendations are intended to optimize the usability of the system, constraints can make it necessary to make “trade-offs” between the application of principles in order to optimize usability. The applicability and the priority given to each principle varies with the specific field of application, user groups and the interaction technique chosen.

# 5.1 Suitability for the user’s tasks

## 5.1.1 Principle
An interactive system is suitable for the user's tasks when it supports the users in the completion of their tasks, i.e. when the operating functions and the user-system interactions are based on the task characteristics (rather than the technology chosen to perform the task).
NOTE 1 A prerequisite for suitability for the user’s tasks is that the tasks themselves have been based on user needs.
NOTE 2 It is important that user-system interactions are based on the task characteristics, rather than the technology chosen to perform the task.
Suitability for the user's tasks involves guidance related to:
- a. identifying suitability of the interactive system for a given task;
- b. optimizing effort in task accomplishment;
- c. defaults supporting the task.

## 5.1.2 Recommendations related to identifying suitability of the interactive system for a given task
### The interactive system should provide sufficient information to enable the users to determine whether the system is appropriate for their intended outcomes.
EXAMPLE 1 The start page of a navigation app concisely identifies the tasks that it supports.
EXAMPLE 2 A parking ticket machine clearly indicates which credit cards it accepts.

## 5.1.3 Recommendations related to optimizing effort in task accomplishment
### 5.1.3.1 The interactive system should provide the user with the controls and task-related information needed for each step of the task.
EXAMPLE 1 A check-in system for flights indicates that a seat can be chosen before the check in process is completed.
NOTE The user needs related to the task determine the required quality, quantity and type of information to be presented.
EXAMPLE 2 A ticket machine for train tickets offers a function for imputing the desired destination and displays the price based on the input.
### 5.1.3.2 The interactive system should avoid imposing steps on the user that are derived from the technology rather than from the needs of the task itself.
NOTE 1 Structuring interaction based on the system's internal data model or internal processing steps can cause unnecessary learning burdens on the user.
EXAMPLE 1 A software application for compressing the size of a file allows the user to first select one or more files to be compressed and then allows the user to compress the file size of all selected files instead of asking the user to first “create an archive” for the files to be compressed.
EXAMPLE 2 A car has an automatic transmission rather than a manual transmission.
NOTE 2 Unnecessary steps include actions assigned to the user that can be more appropriately done automatically by the system.
### 5.1.3.3 The interactive system should avoid offering functionality to the user and presenting information that interferes with completing current tasks.
EXAMPLE 1 A hotel booking system displays only hotels with available rooms for a specific date selected by the user. Information about other hotels in the area is not presented.
EXAMPLE 2 A traffic information display on the street only displays information, if relevant traffic information is present and does not display anything in case there is no traffic information, instead of stating “No traffic information available” which distracts the driver from driving.
NOTE The presentation of inappropriate information can lead to decreased task performance and unnecessary mental workload.

## 5.1.4 Recommendations related to defaults supporting the task
### 5.1.4.1 The interactive system should offer defaults, where appropriate.
NOTE Default values can include standard values, values based on the current context, and values that reflect previous use of the system by the current user.
EXAMPLE 1 A ticket machine at a railway station provides its location as the default station of departure.
EXAMPLE 2 When a user returns to an e-commerce site, the system suggests the last product that user looked at without purchasing it as one of the items that it features.
### 5.1.4.2 The interactive system should avoid defaults, where they can mislead the user.
EXAMPLE 1 A reservation system for restaurants presents the country code of the user's mobile phone when booking a table, only if it can determine which country the person is coming from.
EXAMPLE 2 A teleconferencing system does not automatically turn participant’s microphones in order to avoid creating interferences on the speaker system.
 
Applying these interaction principles and the associated general design recommendations also helps prevent users of those products from experiencing usability problems such as:
- additional unnecessary steps not required as part of the task;
- misleading information;
- insufficient and poor information on the user interface;
- unexpected responses of the interactive system (including those leading to harm from use);
- navigational limitations during use; and
- inefficient error recovery.