from localutils import atlas as at, timetools as tt
import json
import os
import time
import multiprocessing
import ConfigParser
import logging
import itertools


def mes_fetcher(chunk_id, msm, probe_list, start, end, suffix, save_dir):
    """" worker for measurement retrieval

    it fetches the measurement results for a given chunk/list of probes,
    and stores them in json format file, where key is the probe id, value is a dict
    if ping: dict(epoch=[int], min_rtt=[float], all_rtt=[tuple of float])
    if connection: dict(connect=[int], disconnect=[int])
    if traceroute: dict(epoch=[int], paris_id=[int], path=[tuple of hops])

    Args:
        chunk_id (int): the sequential/ID for a chunk of probe IDs
        msm (int): the ID of measurements meant to be feteched
        probe_list (list of int): a chunk of probe IDs
        start (int): epoch time for the beginning of observation window
        end (int): epoch time for the end of observation window
        suffix (string): a string to identify the measurement
        save_dir (string): where the fetched measurement shall be saved
    """
    t1 = time.time()
    mes = at.get_ms_by_pb_msm_id(msm_id=msm, pb_id=probe_list, start=start, end=end)
    if mes:
        with open(os.path.join(save_dir, '%d_%s.json' % (chunk_id, suffix)), 'w') as fp:
            json.dump(mes, fp)
    t2 = time.time()
    logging.info("Chunk %d of measurement %s fetched in %s sec." % (chunk_id, suffix, (t2 - t1)))


def mes_fetcher_wrapper(args):
    """ a wrapper for mes_fetcher

    multiprocessing.Pool.map() doesn't take multiple args, therefore this wrapper
    """
    return mes_fetcher(*args)


def main():
    # log to data_collection.log file
    logging.basicConfig(filename='data_collection.log', level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S %z')

    # load data collection configuration from config file in the same folder
    config = ConfigParser.ConfigParser()
    if not config.read('./config'):
        logging.critical("Config file ./config is missing.")
        return

    # load the configured directory where collected data shall be saved
    try:
        data_dir = config.get("dir", "data")
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        logging.critical("config for data storage is not right.")
        return

    # create data repository if not yet there
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # read configurations for data collection
    try:
        start = config.get("collection", "start")
        end = config.get("collection", "end")
        msmv4 = config.get("collection", "msmv4").split(',')  # multiple msm id can be separated by comma
        msmv4 = [int(i.strip()) for i in msmv4]  # remove the whitespaces and convert to int, could have ValueError
        msmv6 = config.get("collection", "msmv6").split(',')  # do the same for IPv6 measurements
        msmv6 = [int(i.strip()) for i in msmv6]
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError, ValueError):
        logging.critical("config for data collection is not right.")
        return

    # fetch probes/anchors and their meta data
    t1 = time.time()
    probes = at.get_pb(date=tt.string_to_epoch(start))
    probes.extend(at.get_pb(is_anchor=True, date=tt.string_to_epoch(start)))
    t2 = time.time()
    logging.info("Probe query finished in %d sec." % (t2-t1))

    # save probe meta info
    with open(os.path.join(data_dir, "pb.csv"), 'w') as fp:
        fp.write("probe_id;asn_v4;asn_v6;prefix_v4;prefix_v6;is_anchor;country_code;system-tags\n")
        for tup in probes:
            fp.write(';'.join([str(i) for i in tup]) + '\n')

    # filter probes with system tags or with network attributes such as ASN and prefixes
    pb_netv4 = [i[0] for i in probes if (i[1] is not None and i[3] is not None)]
    pb_tagv4 = [i[0] for i in probes if 'system-ipv4-works' in i[-1]]
    pb_netv6 = [i[0] for i in probes if (i[2] is not None and i[4] is not None)]
    pb_tagv6 = [i[0] for i in probes if 'system-ipv6-works' in i[-1]]

    # compare the two ways of filtering
    logging.info("%d/%d probes with not-None v4 ASN and prefixes." % (len(pb_netv4), len(probes)))
    logging.info("%d/%d probes with system-ipv4-works." % (len(pb_tagv4), len(probes)))
    logging.info("%d/%d probes with not-None v6 ASN and prefixes." % (len(pb_netv6), len(probes)))
    logging.info("%d/%d probes with system-ipv6-works." % (len(pb_tagv6), len(probes)))

    logging.info("%d v4 net & tag" % len(set(pb_netv4).intersection(set(pb_tagv4))))
    logging.info("%d v4 net - tag" % len(set(pb_netv4).difference(set(pb_tagv4))))
    logging.info("%d v4 tag - net" % len(set(pb_tagv4).difference(set(pb_netv4))))

    logging.info("%d v6 net & tag" % len(set(pb_netv6).intersection(set(pb_tagv6))))
    logging.info("%d v6 net - tag" % len(set(pb_netv6).difference(set(pb_tagv6))))
    logging.info("%d v6 tag - net" % len(set(pb_tagv6).difference(set(pb_netv6))))

    # collect measurements
    pool = multiprocessing.Pool(multiprocessing.cpu_count())
    # v4 probes for v4 measurements
    task = ((pb_tagv4, msmv4, 'v4'), (pb_tagv6, msmv6, 'v6'))
    for pbs, msm, tid in task:
        # cut the entire list into chunks, each process will work on a chunk
        id_chunks = [pbs[i:i+100] for i in xrange(0, len(pbs), 100)]
        chunk_count = len(id_chunks)
        # probe id to chunk id mapping
        with open(os.path.join(data_dir, "pb_chunk_index_%s.csv" % tid), 'w') as fp:
            fp.write("probe_id;chunk_id\n")
            for chunk_id, probe_list in enumerate(id_chunks):
                for pb in probe_list:
                    fp.write("%d;%d\n" % (pb, chunk_id))
        # iterate over all measurement ids in this task, v4 or v6
        for mid in msm:
            t1 = time.time()
            pool.map(mes_fetcher_wrapper,
                     itertools.izip(xrange(chunk_count), itertools.repeat(mid),
                                    id_chunks, itertools.repeat(start), itertools.repeat(end),
                                    itertools.repeat(str(mid)), itertools.repeat(data_dir)))
            t2 = time.time()
            logging.info("%s Measurements %d fetched in %d sec." % (tid, mid, (t2-t1)))


if __name__ == '__main__':
    main()

