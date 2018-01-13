"""
@Author: Xiaochen (leavebody) Li 
"""
import cv2
import util
import overwatch
import numpy as np
from skimage import measure


class KillfeedAnalyzer:
    """
    Analyze a single killfeed row.
    """
    RIGHT = 1
    LEFT = 0

    def __init__(self, killfeed_image, frame_analyzer):
        """
        @param killfeed_image: The cropped image of a killfeed.
        @param frame_analyzer: The FrameAnalyzer that this killfeed is in.
        """
        self.killfeed_image = killfeed_image

        self.fstruc = frame_analyzer.fstruc
        self.icons = frame_analyzer.killfeed_icons
        self.time = frame_analyzer.time
        self.frame_analyzer = frame_analyzer

        self.killfeed = None

    def get_killfeed(self, title="Default"):
        """
        Get the killfeed in a row.
        @return: None if there is no killfeed in this row; A overwatch.Killfeed object if a killfeed is found in this row.
        """
        if self.killfeed is not None:
            return self.killfeed

        edge_validation = self._validate_edge(self.killfeed_image, title)
        icons_weights = self._get_icons_weights(self.killfeed_image, edge_validation)
        # TODO Only need two best matches in the end. Keep three while debugging.
        best_matches = [KillfeedIconMatch("", -1, -1)] * 3
        for item in icons_weights:
            if item.score > best_matches[0].score:
                best_matches.insert(0, item)
                best_matches.pop()
            elif item.score > best_matches[1].score:
                best_matches.insert(1, item)
                best_matches.pop()
            elif item.score > best_matches[2].score:
                best_matches.pop()
                best_matches.append(item)
        matched_icons = []
        for item in best_matches:
            if item.score < 0.6:  # todo save 0.6 as a constant
                continue
            if edge_validation[item.x]:
                # The metric is that there should be a vertical edge
                # between left 3 pixels to the icon position
                # and right 1 pixel to the icon position
                # with no more than 2 pixels in the vertical line missing.
                # A vertical line should have a width of no more than 2.
                matched_icons.append(item)
        if len(matched_icons) == 0:
            return
        elif len(matched_icons) == 1:
            if matched_icons[0].x < self.fstruc.KILLFEED_MAX_WIDTH - self.fstruc.KILLFEED_CHARACTER2_MAX_WIDTH:
                # If the only icon found is not in the right place, this might be a killfeed that only shows half.
                # Leave it alone for this frame, and deal with it in later frames.
                return
            return self._generate_killfeed(matched_icons)
        else:
            return self._generate_killfeed(matched_icons[:2])

    def _get_icons_weights(self, killfeed_image, edge_validation, name=""):
        """
        Get possible icon and their weights in the killfeed image.
        @param killfeed_image: The killfeed image.
        @param edge_validation: A list of boolean. Should be the result of _validate_edge()
        @param name:
        @return: A list of KillfeedIconMatch object, which includes all possible icons in this killfeed image.
        """
        valid_pixel_count = edge_validation.count(True)
        if valid_pixel_count <= 7:
            return self._get_icons_weights_discrete(killfeed_image, edge_validation, name)
        else:
            return self._get_icons_weights_full(killfeed_image, edge_validation, name)

    def _get_icons_weights_full(self, killfeed_image, edge_validation, name=""):
        """
        Use match template in cv2 to get possible icon and their weights in the killfeed image.
        @param killfeed_image: The killfeed image.
        @param edge_validation: A list of boolean. Should be the result of _validate_edge()
        @param name:
        @return: A list of KillfeedIconMatch object, which includes all possible icons in this killfeed image.
        """
        result = []
        for (object_name, object_icon) in self.icons.ICONS_CHARACTER.iteritems():
            # Match in gray scale
            # killfeed_gray = image.to_gray(killfeed_image)
            # template_gray = image.to_gray(object_icon)
            # match_result = cv2.matchTemplate(killfeed_gray, template_gray, cv2.TM_CCOEFF_NORMED)

            # Match in original color, which seems not really hurting the performance.
            match_result = cv2.matchTemplate(killfeed_image, object_icon, cv2.TM_CCOEFF_NORMED)

            # Find two most possible location of this character's icon in the killfeed image.
            # Mask the pixels around the first location to find the second one.
            _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
            if edge_validation[max_loc[0]]:
                result.append(KillfeedIconMatch(object_name, max_val, max_loc[0]))
            half_mask_width = 5
            mask_index_left = max((max_loc[0] - half_mask_width, 0))
            mask_index_right = min((max_loc[0] + half_mask_width + 1,
                                    self.fstruc.KILLFEED_MAX_WIDTH - self.icons.ICON_CHARACTER_WIDTH))
            match_result[0, mask_index_left: mask_index_right] = [-1] * (mask_index_right - mask_index_left)

            _, max_val, _, max_loc = cv2.minMaxLoc(match_result)
            if edge_validation[max_loc[0]]:
                result.append(KillfeedIconMatch(object_name, max_val, max_loc[0]))
        return result

    def _get_icons_weights_discrete(self, killfeed_image, edge_validation, name=""):
        """
        An alternate way to get weights of icons. Only matches the icon where the pixel passes edge validation.
        Experiments show that when there are less than 8 valid pixels in edge_validation,
        this method is faster than _get_icons_weights_full().
        @param killfeed_image: The killfeed image.
        @param edge_validation: A list of boolean. Should be the result of _validate_edge()
        @param name:
        @return: A list of KillfeedIconMatch object, which includes all possible icons in this killfeed image.
        """
        result_raw = []
        for x in range(len(edge_validation)):
            if not edge_validation[x]:
                continue
            to_compare = util.crop_by_limit(killfeed_image, 0, self.icons.ICON_CHARACTER_HEIGHT, x, self.icons.ICON_CHARACTER_WIDTH)
            best_score = -1
            best_name = ""
            for (object_name, object_icon) in self.icons.ICONS_CHARACTER.iteritems():
                # Matching in original color.
                score = self._match_template_score(to_compare, object_icon)
                if score > best_score:
                    best_score = score
                    best_name = object_name
            result_raw.append(KillfeedIconMatch(best_name, best_score, x))
        mask = [False]*len(edge_validation)
        result_raw.sort(key=KillfeedIconMatch.get_score, reverse=True)
        # print "raw:", result_raw
        result = []
        for match in result_raw:
            if mask[match.x]:
                continue
            mask_left_index = max(0, match.x-5)
            mask_right_index = min(len(mask), match.x+5)
            mask[mask_left_index:mask_right_index] = [True]*(mask_right_index-mask_left_index)
            result.append(match)
        # if len(result)>0:
        #     print name, "discrete", edge_validation.count(True), result
        return result

    @staticmethod
    def _match_template_score(image1, image2):
        """
        Get the TM_CCOEFF_NORMED score of the two input images. Two input image should have the same shape and size.
        @param image1:
        @param image2:
        @return: The TM_CCOEFF_NORMED score of the two input images.
        """
        return cv2.matchTemplate(image1, image2, cv2.TM_CCOEFF_NORMED)[0][0]

    @staticmethod
    def _ssim_score(image1, image2):
        """
        Get the SSIM score of the two input images. Two input image should have the same shape and size.
        @param image1:
        @param image2:
        @return: The SSIM score of the two input images.
        """
        s = measure.compare_ssim(image1, image2, multichannel=True)
        return s

    def _validate_edge(self, killfeed_image, title="default"):
        """
        Use canny to find vertical edges in the killfeed image,
        and use the edges to get the possible positions of icons
        in the killfeed.
        @param killfeed_image: The killfeed image.
        @param title:
        @return: A list of boolean, result[i] is True if there can be a icon starting from x=i,
                and result[i] is false if x=i can starts an icon.
        """
        edge_detection_image = killfeed_image
        edge_image = cv2.Canny(edge_detection_image, 100, 200)  # Generate the edges in this killfeed image.
        edge_span = np.zeros(edge_image.shape)
        for i in range(edge_image.shape[0]):
            for j in range(1, edge_image.shape[1]):
                edge_span[i, j] = sum(edge_image[i, j-1: j+1])  # Get the "spanned" edge image.
        edge_sum = edge_span.sum(0)  # Sum the result on y axis.
        edge_sum = edge_sum/(255 * self.icons.ICON_CHARACTER_HEIGHT)  # Normalize the result.
        edge_validation = [False, False]
        threshold_left = (self.icons.ICON_CHARACTER_HEIGHT - 2.0) / self.icons.ICON_CHARACTER_HEIGHT  # todo save this as constant
        threshold_right = (self.icons.ICON_CHARACTER_HEIGHT - 5.0) / self.icons.ICON_CHARACTER_HEIGHT  # todo save this as constant
        # truecount = 0
        for i in range(2, self.fstruc.KILLFEED_MAX_WIDTH - 38):
            edge_scores_left = edge_sum[i-2: i+2]
            edge_scores_right = edge_sum[i+33: i+37]

            if (max(edge_scores_left) >= threshold_left and
            max(edge_scores_right) >= threshold_right):
                # The metric is that there should be a vertical edge
                # between left 3 pixels to the icon position
                # and right 1 pixel to the icon position
                # with no more than 2 pixels in the vertical line missing.
                # A vertical line should have a width of no more than 2.
                edge_validation.append(True)
                # truecount += 1
            else:
                edge_validation.append(False)
        # print truecount
        edge_validation.extend([False]*6)
        return edge_validation

    def _generate_killfeed(self, matched_icons):
        if len(matched_icons) == 1:
            team = self._get_icon_team(matched_icons[0], self.RIGHT)
            return overwatch.Killfeed("test", self.time, character2=matched_icons[0].object_name, team2=team, event=overwatch.SUICIDE)

        if matched_icons[0].x > matched_icons[1].x:
            matched_icons = [matched_icons[1], matched_icons[0]]

        team1 = self._get_icon_team(matched_icons[0], self.LEFT)
        team2 = self._get_icon_team(matched_icons[1], self.RIGHT)
        event = None
        if team1 == team2:
            event = overwatch.RESURRECTION
        else:
            event = overwatch.ELIMINATION
        return overwatch.Killfeed("test", self.time,
                                  team1=team1, team2=team2,
                                  character1=matched_icons[0].object_name, character2=matched_icons[1].object_name,
                                  event=event)

    def _get_icon_team(self, icon, position):
        """
        Get the team name of an icon in the killfeed.
        @param icon: The KillfeedIconMatch object of this icon.
        @param position: Either self.LEFT or self.RIGHT for the position of this icon in the killfeed.
        @return: The team name of the icon.
        """
        if position == self.LEFT:
            x = icon.x - 5
        elif position == self.RIGHT:
            x = icon.x + self.icons.ICON_CHARACTER_WIDTH + 5
        else:
            raise KeyError("position must be KillfeedAnalyzer.LEFT or KillfeedAnalyzer.RIGHT")
        color = self.killfeed_image[0][x]
        team1_distance = util.color_distance(color, self.frame_analyzer.game.color_team1)
        team2_distance = util.color_distance(color, self.frame_analyzer.game.color_team2)

        if team1_distance <= team2_distance:
            return self.frame_analyzer.game.name_team1
        else:
            return self.frame_analyzer.game.name_team2


class KillfeedIconMatch:
    """
    A helper class to store the intermediate result of a recognized icon in the killfeed.
    """
    def __init__(self, object_name, score, x):
        #: The name of the recognized object.
        self.object_name = object_name
        #: The score of this match.
        self.score = score
        #: The x coordinate of the recognized object in the killfeed image.
        self.x = x

    def __str__(self):
        return "KillfeedIconMatch<"+self.object_name+", "+str(self.score)+", "+str(self.x)+">"
    __repr__ = __str__

    @staticmethod
    def get_score(match):
        return match.score