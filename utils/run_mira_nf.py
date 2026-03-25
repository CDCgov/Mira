# General python packages
import os
import sys
import time
import asyncio
import argparse
import logging

# ----------------------------
# Logger setup
# ----------------------------
logger = logging.getLogger("runMiraNf")
logger.setLevel(logging.DEBUG)


# ----------------------------
# Redirect print() to logger
# ----------------------------
class LoggerWriter:
    def __init__(self, log_func, stream):
        self.log_func = log_func
        self.stream = stream

    def write(self, message):
        message = message.rstrip()
        if message:
            self.log_func(message)
            self.stream.write(message + "\n")
            self.stream.flush()

    def flush(self):
        self.stream.flush()


# ----------------------------
# Setup logging
# ----------------------------
def setup_logging(log_file_path):
    log_file_path = os.path.realpath(log_file_path.strip())

    # File handler
    file_handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Redirect stdout/stderr → logger + console
    sys.stdout = LoggerWriter(logger.info, sys.__stdout__)
    sys.stderr = LoggerWriter(logger.error, sys.__stderr__)

    print(f"SEE LOGS AT {log_file_path} FOR MORE DETAILS")
    return logger


# ----------------------------
# Async function to run MIRA-NF
# ----------------------------
async def mira_nf_kickoff(
    data_root,
    seq_run,
    experiment_type,
    amplicon_library,
    parquet_files,
    nextclade,
    command_type
):
    # Base command
    if command_type == "docker":
        cmd = (
            "docker exec mira-nf nextflow run /MIRA-NF/main.nf "
            f"-profile mira_nf_container "
            f"--input /data/{seq_run}/samplesheet.csv "
            f"--runpath /data/{seq_run} "
            f"--outdir /data/{seq_run}/mira_results "
        )
    elif command_type == "bash":
        cmd = (
            "nextflow run /MIRA-NF/main.nf "
            f"-profile mira_nf_container "
            f"--input /data/{seq_run}/samplesheet.csv "
            f"--runpath /data/{seq_run} "
            f"--outdir /data/{seq_run}/mira_results "
        )
    else:
        raise ValueError(f"Invalid command_type: {command_type}")

    # Append other flags
    cmd += f"--e {experiment_type} "
    cmd += f"--parquet_files {parquet_files} "
    cmd += f"--nextclade {nextclade} "

    if experiment_type in ["SC2-Whole-Genome-Illumina", "RSV-Illumina"]:
        cmd += f"-p {amplicon_library} "

    logger.info(f"Running command: {cmd}")

    # Launch subprocess
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Stream output live to logger
    async def stream_output(stream, log_func):
        lines = []
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="ignore").rstrip()
            log_func(text)
            lines.append(text)
        return "\n".join(lines)

    stdout, stderr = await asyncio.gather(
        stream_output(proc.stdout, logger.info),
        stream_output(proc.stderr, logger.error),
    )

    await proc.wait()

    if proc.returncode != 0:
        logger.error(f"MIRA-NF failed with return code {proc.returncode}")
        raise RuntimeError(f"MIRA-NF failed with return code {proc.returncode}\n{stderr}")

    logger.info(f"MIRA-NF finished successfully with return code {proc.returncode}")
    return proc.returncode, stdout, stderr


# ----------------------------
# Main entrypoint
# ----------------------------
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="RUN MIRA-NF WITH LOGGING")

    parser.add_argument("--data_root", type=str, required=True)
    parser.add_argument("--seq_run", type=str, required=True)
    parser.add_argument("--experiment_type", type=str, required=True)
    parser.add_argument("--command_type", type=str, required=True)

    parser.add_argument("--amplicon_library", type=str, default=None)
    parser.add_argument("--nextclade", type=str, default=False)
    parser.add_argument("--parquet_files", type=str, default=False)

    parser.add_argument("--log_file", type=str, required=True)

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_file)

    # ----------------------------
    # Run pipeline
    # ----------------------------
    start = time.time()

    try:
        loop = asyncio.get_running_loop()
        # Already inside loop → just await
        task = loop.create_task(
            mira_nf_kickoff(
                data_root=args.data_root,
                seq_run=args.seq_run,
                experiment_type=args.experiment_type,
                amplicon_library=args.amplicon_library,
                parquet_files=args.parquet_files,
                nextclade=args.nextclade,
                command_type=args.command_type
            )
        )
        loop.run_until_complete(task)
    except RuntimeError:
        # No loop → safe to use asyncio.run
        asyncio.run(
            mira_nf_kickoff(
                data_root=args.data_root,
                seq_run=args.seq_run,
                experiment_type=args.experiment_type,
                amplicon_library=args.amplicon_library,
                parquet_files=args.parquet_files,
                nextclade=args.nextclade,
                command_type=args.command_type
            )
        )

    end = time.time()
    logger.info(f"Total time: {(end - start)/60:.2f} minutes")