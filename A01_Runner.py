# Investment Runner

'''
The purpose of this program is to run all the other files so that
we do not have to complete this process manually. This enhances the 
efficiency and flexibility of the system itself. 
'''

# Import the necessary modules
import subprocess
import sys

# Define a list and a for loop to run the whole pipeline 
scripts = ['A02_Parser.py', 'A03_DataAnalyzer.py']
for script in scripts:
    result = subprocess.run([sys.executable, script], capture_output = True, text = True)

    if result.returncode != 0:
        print(f'The {script} failed. Stopping pipeline')

        # Display the actual error
        print('Error Message: ')
        print(result.stderr)

        # Break the loop
        break