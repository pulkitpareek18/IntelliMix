import csv

def read_csv(file_path):
    url_start_end = []
    with open(file_path, mode='r', newline='') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            start = row['Start']
            end = row['End']

            # Convert MM:SS format to seconds
            if ':' in start:
                minutes, seconds = map(int, start.split(':'))
                start = minutes * 60 + seconds
            else:
                start = int(start)

            if ':' in end:
                minutes, seconds = map(int, end.split(':'))
                end = minutes * 60 + seconds
            else:
                end = int(end)

            url_start_end.append([row['Url'], start, end])
    return url_start_end