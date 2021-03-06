from __future__ import annotations
import subprocess
from typing import List

from src.constants import (
    COMMAND_EXIT_ERROR_MESSAGE,
    MAX_ACCEPTABLE_AVERAGE_ROUND_TRIP_TIME,
    MAX_ACCEPTABLE_PACKET_LOSS,
    LOCAL_ROUTER_ERROR,
    MODEM_ERROR,
    PACKET_LOSS_ERROR,
    PING_COMMAND,
    PING_COUNT_OPTION,
    PING_QUIET_COMMAND,
    RESOLVE_HOST_ERROR,
    RESPONSE_KEY_ERROR,
    RESPONSE_KEY_HOST,
    RESPONSE_KEY_NUM_PACKETS_SENT,
    RESPONSE_KEY_PACKET_LOSS_PERCENT,
    RESPONSE_KEY_MAX_ROUND_TRIP_TIME,
    RESPONSE_KEY_AVERAGE_ROUND_TRIP_TIME,
    RESPONSE_KEY_ABLE_TO_RESOLVE_HOST,
    ROUND_TRIP_TIME_ERROR
)
from src.logger import logger
from src.sec_constants import LOCAL_ROUTER


class Ping:

    def ping_host_and_return_parsed_response(
            self: Ping,
            url: str,
            num_pings: int = 10) -> dict:
        '''
        Pings a given host and returns a parsed dictionary response.
        Returned dictionary has example format:
        {
            host: 'www.google.com',
            num_packets_sent: 10,
            packet_loss_percent: 5.0,
            max_round_trip_time: 3.723,
            average_round_trip_time: 2.123
            able_to_resolve_host: True,
            error: ''
        }
        If ping is unsuccessful and unable to resolve host, the returned
        dictionary has the same format but with only the 'host' and the
        'able_to_resolve_host' field, which is False.
        '''
        response = self.ping_host(url, num_pings)
        logger.log_verbose(response)
        parsed_ping_dict = self.parse_ping_response(url, response)
        if not parsed_ping_dict[RESPONSE_KEY_ERROR]:
            self.check_if_ping_was_successful(parsed_ping_dict)
        return parsed_ping_dict

    def ping_host(self: Ping, url: str, num_pings: int) -> str:
        try:
            response = subprocess.check_output(
                [PING_COMMAND, PING_COUNT_OPTION, str(num_pings),
                 PING_QUIET_COMMAND, url],
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
        except subprocess.CalledProcessError as error:
            response = str(error)
        return response

    def parse_ping_response(self: Ping, url: str, response: str) -> dict:
        '''
        Parses an initial response into a dictionary with the parsed ping
        response.
        '''
        parsed_ping_dict = {
            RESPONSE_KEY_HOST: url,
            RESPONSE_KEY_ABLE_TO_RESOLVE_HOST: False,
            RESPONSE_KEY_ERROR: None
        }
        split_ping_response = response.splitlines()

        ping_executed_successfully = \
            self.check_if_ping_executed_successfully(split_ping_response)
        if not ping_executed_successfully:
            if url == LOCAL_ROUTER:
                parsed_ping_dict[RESPONSE_KEY_ERROR] = LOCAL_ROUTER_ERROR
            else:
                parsed_ping_dict[RESPONSE_KEY_ERROR] = MODEM_ERROR
            return parsed_ping_dict

        ping_was_able_to_resolve_host = \
            self.determine_if_able_to_resolve_host(
                url, split_ping_response)
        if not ping_was_able_to_resolve_host:
            return parsed_ping_dict

        parsed_ping_dict[RESPONSE_KEY_ABLE_TO_RESOLVE_HOST] = True

        # Parse appropriate metrics and update parsed_ping_dict
        ping_summary_response = split_ping_response[-2]
        self.parse_ping_summary_and_update_parsed_ping_dict(
            parsed_ping_dict, ping_summary_response)

        ping_timing_response = split_ping_response[-1]
        self.parse_ping_timing_and_update_parsed_ping_dict(
            parsed_ping_dict, ping_timing_response)
        return parsed_ping_dict

    def parse_ping_summary_and_update_parsed_ping_dict(
            self: Ping, parsed_ping_dict: dict, ping_summary: str) -> None:
        '''
        Parses the given ping summary and updates the parsed_ping_dict.

        Example ping summary:
        10 packets transmitted, 10 packets received, 0.0% packet loss
        '''

        split_ping_summary = ping_summary.split(',')

        # Get packets transmitted
        packets_transmitted_data = split_ping_summary[0]
        parsed_ping_dict[RESPONSE_KEY_NUM_PACKETS_SENT] = \
            int(packets_transmitted_data.split(' ')[0])

        # Get packet loss percentage
        # Sometimes there may be multiple errors that make the packet loss
        # index change
        for metric in split_ping_summary:
            if 'packet loss' in metric:
                packet_loss_data = metric
                parsed_ping_dict[RESPONSE_KEY_PACKET_LOSS_PERCENT] = \
                    float(packet_loss_data.split('%')[0])

    def parse_ping_timing_and_update_parsed_ping_dict(
            self: Ping, parsed_ping_dict: dict, ping_timing: str) -> None:
        '''
        Parses the given ping timing and updates the parsed_ping_dict.

        Example ping timing:
        round-trip min/avg/max/stddev = 3.084/8.829/11.708/2.290 ms
        '''

        split_ping_timing = ping_timing.split('=')
        split_ping_timing = split_ping_timing[1].split('/')

        # Get average timing
        parsed_ping_dict[RESPONSE_KEY_AVERAGE_ROUND_TRIP_TIME] = \
            float(split_ping_timing[1])

        # Get max timing
        parsed_ping_dict[RESPONSE_KEY_MAX_ROUND_TRIP_TIME] = \
            float(split_ping_timing[2])

    def check_if_ping_executed_successfully(
            self: Ping,
            split_ping_response: List[str]) -> bool:
        '''
        If not able to connect to local router, the ping fails and exits with
        a message that contains the following in the string:
        returned non-zero exit status
        '''
        if COMMAND_EXIT_ERROR_MESSAGE in split_ping_response[0]:
            return False
        return True

    def determine_if_able_to_resolve_host(
            self: Ping,
            url: str,
            split_ping_response: str) -> bool:
        '''
        Determines if ping was able to resolve host.
        Successful pings have a multiline response while unsuccessful pings
        are a single line.
        '''
        if len(split_ping_response) == 1:
            return False
        return True

    def check_if_ping_was_successful(
            self: Ping,
            parsed_host_response: dict) -> None:

        if not self.check_if_ping_resolve_host(parsed_host_response):
            parsed_host_response[RESPONSE_KEY_ERROR] = RESOLVE_HOST_ERROR

        elif not self.check_if_ping_packet_loss_acceptable(
                parsed_host_response):
            parsed_host_response[RESPONSE_KEY_ERROR] = PACKET_LOSS_ERROR

        elif not self.check_if_ping_round_trip_time_acceptable(
                parsed_host_response):
            parsed_host_response[RESPONSE_KEY_ERROR] = \
                ROUND_TRIP_TIME_ERROR

        else:
            parsed_host_response[RESPONSE_KEY_ERROR] = ''

    def check_if_ping_resolve_host(
            self: Ping,
            parsed_host_response: dict) -> bool:
        return parsed_host_response[RESPONSE_KEY_ABLE_TO_RESOLVE_HOST]

    def check_if_ping_packet_loss_acceptable(
            self: Ping,
            parsed_host_response: dict) -> bool:
        if (parsed_host_response[RESPONSE_KEY_PACKET_LOSS_PERCENT] >
                MAX_ACCEPTABLE_PACKET_LOSS):
            return False
        return True

    def check_if_ping_round_trip_time_acceptable(
            self: Ping,
            parsed_host_response: dict) -> bool:
        if (parsed_host_response[RESPONSE_KEY_AVERAGE_ROUND_TRIP_TIME] >
                MAX_ACCEPTABLE_AVERAGE_ROUND_TRIP_TIME):
            return False
        return True
