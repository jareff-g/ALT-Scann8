#!/bin/bash

# Set the path to the directory containing your files
target_folder="."

# Set the range of file numbers (1 to n)
start_number=1

# Iterate through files in numerical order
number=$start_number
while [ 1 ]; do
    # Format the number with leading zeros
    source_file_1=$(printf "hdrpic-%05d.1.jpg" "$number" )
    source_file_2=$(printf "hdrpic-%05d.2.jpg" "$number" )
    source_file_3=$(printf "hdrpic-%05d.3.jpg" "$number" )
    source_file_4=$(printf "hdrpic-%05d.4.jpg" "$number" )
    target_file=$(printf "picture-%05d.jpg" "$number" )

    # Check if the file exists
    if [ -f "$source_file_1" ] && [ -f "$source_file_2" ] && [ -f "$source_file_3" ] && [ -f "$source_file_4" ]; then
        enfuse --output="$target_file" "$source_file_1" "$source_file_2" "$source_file_3" "$source_file_4"
        echo "Processing files for number $number"
    else
        break
    fi
    ((number++))
done
