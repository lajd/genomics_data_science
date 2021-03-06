import os
from abc import ABC, abstractmethod
import random
from typing import Optional, List, Type
import bisect
from collections import defaultdict, deque
from matplotlib import pyplot as plt
from courses.course_3_algorithms_for_dna_seq.algorithms_for_dna_sequencing_week_1 import readGenome

from data import DATA_DIR

from courses.course_3_algorithms_for_dna_seq.utils.boyer_moore_preproc import BoyerMoorePreprocessing


class ExactMatchingStrategy(ABC):
    @abstractmethod
    def get_occurrences(self, **kwargs):
        pass


### Boyer-Moore basics
class BoyerMooreExact(ExactMatchingStrategy):
    def __init__(self, p: str, p_bm: Optional[BoyerMoorePreprocessing] = None, alphabet: str = 'ACGT', **kwargs):
        if not p_bm:
            p_bm = BoyerMoorePreprocessing(p, alphabet=alphabet)
        self.p = p
        self.p_bm = p_bm

    def get_occurrences(self, t: str, **kwargs):
        return self.query(t)[0]

    def query(self, t: str):
        occurrences = []
        skipped_alignments = []
        num_char_comparisons = 0
        alignment_start_idx = 0
        num_alignments_tried = 0

        while alignment_start_idx <= (len(t) - len(self.p)):
            num_alignments_tried += 1
            shift = 1
            match = True
            # Check from right to left
            for j in range(len(self.p) - 1, -1, -1):
                num_char_comparisons += 1
                k = alignment_start_idx + j
                if self.p[j] != t[k]:
                    match = False
                    bad_char_shift = self.p_bm.bad_character_rule(j, t[k])
                    good_suffix_shift = self.p_bm.good_suffix_rule(j)
                    shift = max(bad_char_shift, good_suffix_shift, shift)
                    if shift > 1:
                        skipped_alignments.append(
                            {
                                'shift': shift - 1,
                                'bad_char_shift':  bad_char_shift - 1 if bad_char_shift > 0 else 0,
                                'good_suffix_shift': good_suffix_shift - 1 if good_suffix_shift > 0 else 0
                            }
                        )
                    break

            if match:
                occurrences.append(alignment_start_idx)
                skip_gs = self.p_bm.match_skip()
                shift = max(shift, skip_gs)
            alignment_start_idx += shift
        return occurrences, num_alignments_tried, num_char_comparisons


class SubseqIndex(ExactMatchingStrategy):
    """ Holds a subsequence index for a text T """

    def __init__(self, t, k, ival=1, **kwargs):
        """ Create index from all subsequences consisting of k characters
            spaced ival positions apart.  E.g., SubseqIndex("ATAT", 2, 2)
            extracts ("AA", 0) and ("TT", 1). """
        self.t = t
        self.k = k  # num characters per subsequence extracted
        self.ival = ival  # space between them; 1=adjacent, 2=every other, etc
        self.index = []
        self.span = 1 + ival * (k - 1)
        for i in range(len(t) - self.span + 1):  # for each subseq
            self.index.append((t[i:i + self.span:ival], i))  # add (subseq, offset)
        self.index.sort()  # alphabetize by subseq

    def get_hits(self, p):
        """ Return index hits for first subseq of p """
        subseq = p[:self.span:self.ival]  # query with first subseq
        i = bisect.bisect_left(self.index, (subseq, -1))  # binary search
        hits = []
        while i < len(self.index):  # collect matching index entries
            if self.index[i][0] != subseq:
                break
            hits.append(self.index[i][1])
            i += 1
        return hits

    def get_occurrences(self, p: str, **kwargs):
        # k = self.k
        # offsets = []
        # for i in self.get_hits(p):
        #
        #     if p[k:] == self.t[i+k:i+len(p)]:
        #         offsets.append(i)
        return self.get_hits(p)
        # return sorted(offsets)


class PigeonHoleApproximateMatching:

    @staticmethod
    def query_bm(p: str, t: str, m: int, alphabet='ACGT'):
        partition_length = int(round(len(p) / (m + 1)))
        occurrences = set()
        total_hits = 0
        for i in range(m + 1):
            partition_start = i * partition_length
            partition_end = min(partition_start + partition_length, len(p))
            sub_p = p[partition_start:partition_end]
            if not sub_p:
                break

            matcher = BoyerMooreExact(p=sub_p, alphabet=alphabet)
            occurrences_ = matcher.get_occurrences(p=sub_p, alphabet=alphabet, t=t)
            # bm = BoyerMooreExact(sub_p, alphabet=alphabet)
            # occurrences_, alignments_tried_, num_comparisons_ = bm.query(t)

            # For any exact matches found, perform a validation step. Look around the exact match,
            # and see if the text matches (allowing a certain number of mismatches). If the text
            # matches within a certain number of mismatches, we have found a match
            for match in occurrences_:
                total_hits += 1
                # This match occurs outside of the range of this partition, once aligned with t
                if match < partition_start or (match - partition_start + len(p)) > len(t):
                    continue
                else:
                    mismatches = 0

                    # Test the part of p before the partition we already compared above
                    for j in range(0, partition_start):
                        if p[j] != t[match - partition_start + j]:
                            mismatches += 1
                            if mismatches > m:
                                break
                    # Compare section after the segment already tested
                    for j in range(partition_end, len(p)):
                        if p[j] != t[match - partition_start + j]:
                            mismatches += 1
                            if mismatches > m:
                                break

                    if mismatches <= m:
                        occurrences.add(match - partition_start)
        return sorted(occurrences), total_hits

    @staticmethod
    def query_subseq_index(p: str, t: str, m: int, ival: int = 1, k: Optional[int] = None):
        if not k:
            k = max(int(round(len(p) / (m + 1))), int(len(p)/2))

        all_matches = set()
        p_idx = SubseqIndex(t, k=k, ival=ival)
        idx_hits = 0
        for i in range(m + 1):
            start = i
            matches = p_idx.get_occurrences(p[start:])

            # Extend matching segments to see if whole p matches
            for m in matches:
                idx_hits += 1
                if m < start or m - start + len(p) > len(t):
                    continue
                else:
                    mismatches = 0

                    for j in range(0, len(p)):
                        if p[j] != t[m - start + j]:
                            mismatches += 1
                            if mismatches > m:
                                break

                    if mismatches <= m:
                        all_matches.add(m - start)
        return sorted(all_matches), idx_hits
