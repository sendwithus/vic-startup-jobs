#!/usr/bin/env bash

# Check deps
if ((BASH_VERSINFO[0] < 4)); then
	echo "You need bash 4 or later to run this script."
	echo "Bash version: ${BASH_VERSION}"
	exit 1
fi

if ! command -v curl &> /dev/null ; then
	echo "You need cURL to run this script."
	exit 1
else
	# Print the curl version and sort it against what we require.
	# If we get our version back, the installed version is greater.
	# It's also likely safe enough to parse versions with head and cut,
	# curl 4.8 from 1998 printed versions in the same way as curl does now.
	curl_vhave=$(curl --version | head -n1 | cut -d ' ' -f2)
	curl_vneed=$(printf '6.5.1\n%s\n' "$curl_vhave" | sort -r -n | head -n1)

	if [[ "$curl_vhave" != "$curl_vneed" ]]; then
		echo "You need at least cURL 6.5.1 to run this script."
		echo "cURL version: ${curl_vhave}"
		exit 1
	fi
fi

find_links () {
	# This function creates an associative array of markdown link text to
	# URL. It takes one arguement, a markdown filename to search within.
	filename=$1

	# Declare an associative array in global scope
	declare -A LINKS

	# Regex pattern to isolate [text](url) markdown links
	regexp='\[[^\]+\]\([^\)]+\)'

	# Another regex pattern to extract / convert markdown links
	# into a mapfile; format "text"<tab>url
	convert_markdown='s#\[(.*)\]\((.*)\)#"\1"\t\2#p'

	# Read a mapfile into a normal non-associative array
	readarray -t linkmap < <(grep -oE "$regexp" "$filename" | sed -rn "$convert_markdown")

	for line in "${linkmap[@]}"; do
		# For the lines in the mapfile,
		# the keys are everything before a tab...
		key="${line%$'\t*'}"
		# ... and the values are everything after
		value="${line##$'*\t'}"

		# Assign to the associative array.
		# This whole loop body could just have been
		# LINKS["${line%$'\t*'}"]="${line##$'*\t'}",
		# but that's a little cryptic, no?
		LINKS[$key]=$value
	done

	[[ ! $QUIET ]] && echo >&2 "📊 Found ${#LINKS[@]} links in this document to test."
	[[ $MARKDOWN ]] && echo "Checkboxes for links to remove: "

	_queue_link_tests
	exit_code=$?

	[[ ! $QUIET ]] && echo >&2 "✨ Done checking! [${exit_code} problem(s)]"

	exit "$exit_code"
}


test_link () {

	link=$1
	text=$2

	# Some URL component extraction
	scheme=$(grep :// <<< "$link" | sed -e 's#^\(.*://\).*#\1#g')
	if [[ -z "$scheme" ]]; then
		# Didn't find a scheme, maybe it's a mailto link?
		# check for that explicitly
		scheme=$(grep mailto: <<< "$link" | sed -e 's#^\(mailto:\).*#\1#g')
	fi
	url="${link/${scheme}/}"
	user=$(grep @ <<< "$url" | cut -d@ -f1)
	hostport=$(cut -d/ -f1 <<< "${url/${user}@/}")

	# Paterns to filter on
	hash_or_slash='^[\.#/]'
	http_or_https='^https?://'
	mailto='^mailto:'
	if [[ "${link}" =~ $hash_or_slash ]]; then
		[[ ! $QUIET ]] && echo >&2 "🔗 Skip: ${link} seems more like an anchor or local file."
		return 0 # Skiping is OK, we warned

	elif [[ "${link}" =~ $mailto ]]; then
		# Could write $hostport to $link, and check that the email's domain resolves,
		# or bring in other dependency to check for an MX record.. but meh - no-one
		# seems to actually be posting jobs with email links
		[[ ! $QUIET ]] && echo >&2 "📮 Skip: ${link} starts with mailto, let's hope it exists!"
		return 0 # Skiping is OK, we warned

	elif [[ ! "${scheme}" =~ $http_or_https || -z "${scheme}" ]]; then
		[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (Missing or unknown scheme)"
		[[ ! $QUIET ]] && echo >&2 "🦺 Skip: The scheme component on ${link} isn't http(s) or is empty."
		return 1 # Missing scheme, www.example.com will be linked to a file in the repo

	else
		http_code=$(curl --location --silent -o /dev/null -w '%{http_code}' "${link}")
		curl_status=$?

		# We follow redirects (--location), but 3xx-series HTTP codes could still end up here.
		# 300 (Multiple Choice) is an example, so let's report on anything >= 300.
		# Codes for reference: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
		if [[ "$http_code" -ge 300 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] ${http_code} ${text} ${link}"
			[[ ! $QUIET ]] && echo >&2 "👻 [${http_code}] ${text} seems gone, from ${hostport}"
			return 1 # HTTP error, this is what this whole script for here for
		fi

		# See https://curl.haxx.se/libcurl/c/libcurl-errors.html for more cases we might
		# want to handle.
		if [[ "$curl_status" -eq 6 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (UNRESOLVED HOST)"
			[[ ! $QUIET ]] && echo >&2 "🌎 [---] DNS lookup didn't resolve ${hostport}."
			return 1 # Failed DNS

		elif [[ "$curl_status" -eq 7 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (COULDNT'T CONNECT TO SERVER)"
			[[ ! $QUIET ]] && echo >&2 "📡 [---] Couldn't connect to ${hostport}."
			return 1 # Coudn't connect

		elif [[ "$curl_status" -eq 28 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (TIMEOUT WAS REACHED)"
			[[ ! $QUIET ]] && echo >&2 "⌛ [---] Timed out with ${hostport}."
			return 1 # Timed out

		elif [[ "$curl_status" -eq 35 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (FAILED SSL HANDSHAKE)"
			[[ ! $QUIET ]] && echo >&2 "🤝 [---] Handshaking with ${hostport} failed."
			return 1 # Failed SSL

		elif [[ "$curl_status" -eq 60 || "$curl_status" -eq 51 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (FAILED SSL VERIFICATION)"
			[[ ! $QUIET ]] && echo >&2 "🔓 [---] ${hostport}'s SSL certificate seems invalid!"
			return 1 # Failed SSL

		elif [[ "$curl_status" -eq 130 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (SIGINT)"
			[[ ! $QUIET ]] && echo >&2 "🛑 [---] Interrupted checking ${hostport}!"
			return 1 # Interrupted

		elif [[ ! "$curl_status" -eq 0 ]]; then
			[[ $MARKDOWN ]] && echo "* [ ] --- ${text} ${link} (CURLcode: ${curl_status})"
			[[ ! $QUIET ]] && echo >&2 "🤷 [---] Checking ${hostport} failed with CURLcode ${curl_status}"
			return 1 # cURL's unhappy, I'm unhappy
		fi

		# Codes are OK
		return 0
	fi

	# Bad logic? Maybe forgot about some case? => fail
	return 1
}



# This bash background processing queue works by creating a named pipe
# and writing return codes to it. In order for a new task to start
# it must first read 000 (success) return code from an earlier job
# then write it's own return code back to the queue to signify being
# done.

_open_bg_queue () {
	# Start a queue for controlling how many background processes can run
	# at once. This function takes 1 argument - the number of concurrent
	# tasks to run at once.
	local N=$1

	# Make a named pipe to signal when background processes can be run
	queue=$(mktemp -u)
	mkfifo -m 600 "$queue"

	# Make another named pipe to collect return codes
	return=$(mktemp -u)
	mkfifo -m 600 "$return"

	# Open fd 3 and 4 for r/w. Unlink them now to ease cleanup, but
	# they won't be removed until their fd closes.
	exec 3<>"$queue"
	exec 4<>"$return"
	rm "$queue" "$return"

	# Pre-populate the pipe with N semaphores / tokens
	for (( ; N > 0; N-- )) ; do
		printf %s 000 >&3
	done
}


_bg_task () {
	# Run a task in the background queue. This function waits
	# for a token from the queue on fd 3, then runs it's arguments
	# as a command in a subshell, and writes a continue token
	# back to the queue.

	# Wait until fd 3 can have 3 characters read from it,
	# then continue - or exit if the read token isn't 000
	local x
	if read -r -u 3 -n 3 x ; then
		if (( x != 0 )) ; then
			echo "Invalid background task token [${x}]. Exiting."
			exit 1
		fi
	fi

	# This subshell runs the command in the background
	# and pushes it's return code ($?) to the fd 3 queue
	(
		{ "$@"; }

		# Write the 3 digit return code for collection later
		printf "%.3d" $? >&4

		# Write 000 as a continue token
		printf '%.3d' 0 >&3
	)&
}

_queue_link_tests () {
	# This function simply opens a background queue with N
	# workers, and queues up all the links we found earlier
	# to be checked.

	_open_bg_queue "$WORKERS"

	# Use an array as a set to only check each link once,
	# in case the same link appears multiple times,
	# such as with a /careers page
	local -a tested

	# Iterate over the keys of the LINKS assocative array
	for text in "${!LINKS[@]}"; do
		link=${LINKS[$text]}

		# Using a space as a separator, join the links in the
		# tested array then check if $link is a substring of it.
		# This is a one-liner array includes operation.
		if [[ ! " ${tested[*]} " == *" ${link} "* ]]; then
			# Haven't seen this link before
			tested+=("${link}")

			# Queue it up
			_bg_task test_link "${link}" "${text}"
		else
			[[ ! $QUIET ]] && echo >&2 "💫 Skip: Already saw ${link}."
		fi
	done

	wait # for all child tasks

	# Now read out all the return codes and return the count.
	# Time out in 1/2 second to let us break out of this loop,
	# since we now expect all the results to be written already.
	local ret=0 count=0
	while read -r -u 4 -n 3 -t 0.5 ret ; do
		count=$(( count + ret ))
	done

	return "$count"
}


# Argument defaults
QUIET=
MARKDOWN=
WORKERS=4
INPUT_FILE=/dev/stdin

# Argument parsing
while test $# -gt 0; do
	case $1 in
		-h|--help)
			echo "Scans Markdown documents for links that don't resolve."
			echo
			echo "Usage:"
			echo " $ ${0} [INPUT_FILE] [-w N] [-q] [-m]"
			echo
			echo "Options:"
			echo " -w | --workers : Integer"
			echo "    Number of background tasks to use while link checking"
			echo
			echo " -q | --quiet : Flag"
			echo "    Do not ouput logs on the standard error stream."
			echo
			echo " -m | --markdown : Flag"
			echo "    Enable markdown checkbox list creation on standard output"
			echo
			echo "Example:"
			echo " $ ${0} -w 10 README.md --markdown > bad-links.md"
			echo
			exit 0
		;;

		-w|--workers)
			_workers_flag=$1
			shift
			if test $# -gt 0; then
				WORKERS=$1

				if [[ ! "$WORKERS" -eq "$WORKERS" || "$WORKERS" -le 0 ]] 2>/dev/null ; then
					echo >&2 "Workers: ${_workers_flag} flag expects an integer greater than 0"
					exit 1
				fi
			else
				echo "Workers: No number of workers specified"
				exit 1
			fi
			shift
		;;
		--workers=*)
			_workers_flag='--workers'
			WORKERS="${1//--workers=/}"
			shift

			if [[ ! "$WORKERS" -eq "$WORKERS" || "$WORKERS" -le 0 ]] 2>/dev/null ; then
				echo >&2 "Workers: ${_workers_flag} flag expects an integer greater than 0"
				exit 1
			fi
		;;

		-q|--quiet)
			shift
			QUIET=1
		;;

		-m|--markdown)
			shift
			MARKDOWN=1
		;;

		*)
			if [[ -r $1 ]]; then
				INPUT_FILE=$1
				shift
			else
				echo "Input: ${1} does not represent a readable file"
				exit 1
			fi
		;;
	esac
done

if [[ "$INPUT_FILE" == "/dev/stdin" && -t 0 ]]; then
	{
		echo "STDIN is a tty! Naively refusing to continue."
		echo
		echo "Provide a filename, or pipe input to this script:"
		echo " $ ${0} [FILENAME]"
		echo " $ cat [FILENAME] | ${0}"
	} >&2
	exit 1
fi

find_links "$INPUT_FILE"
