function charaOnField = detectCharasOnField(oneFrame, charaNamesArr, charaIconsArr)



charaOnField = {};
width = 38;
height = 30;

%% Left
teamColor = oneFrame(1, 1, :);
bgimage = zeros(25, 32, 3);
bgimage(:, :, 1) = teamColor(1);
bgimage(:, :, 2) = teamColor(2);
bgimage(:, :, 3) = teamColor(3);
bgimage = double(bgimage);

for i = 1:6
    xmin = 62 + (i-1) * 71;
    ymin = 48;
    charaIcon = imcrop(oneFrame,[xmin,ymin,width,height]);
    for j = 1:size(charaNamesArr,2)
        icon = charaIconsArr{j, 1};
        alpha = charaIconsArr{j, 2};
        fusedIcon = uint8(icon.*(alpha/255) + bgimage.*((255-alpha)/255));
        corr1 = max(max(normxcorr2(fusedIcon(:, :, 1),charaIcon(:, :, 1))));
        corr2 = max(max(normxcorr2(fusedIcon(:, :, 2),charaIcon(:, :, 2))));
        corr3 = max(max(normxcorr2(fusedIcon(:, :, 3),charaIcon(:, :, 3))));
        corr = (corr1 + corr2 + corr3)/3;
        judgeGray(j) = corr;
    end
    [r2,c2] = find(judgeGray == max(judgeGray));
    charaOnField{i} = charaNamesArr{c2};
end

%% right
teamColor = oneFrame(1, 1280, :);
bgimage = zeros(25, 32, 3);
bgimage(:, :, 1) = teamColor(1);
bgimage(:, :, 2) = teamColor(2);
bgimage(:, :, 3) = teamColor(3);
bgimage = double(bgimage);

for i = 1:6
    xmin = 857 + (i-1) * 71;
    ymin = 48;
    charaIcon = imcrop(oneFrame,[xmin,ymin,width,height]);
    for j = 1:size(charaNamesArr,2)
        icon = charaIconsArr{j, 1};
        alpha = charaIconsArr{j, 2};
        fusedIcon = uint8(icon.*(alpha/255) + bgimage.*((255-alpha)/255));
        corr1 = max(max(normxcorr2(fusedIcon(:, :, 1),charaIcon(:, :, 1))));
        corr2 = max(max(normxcorr2(fusedIcon(:, :, 2),charaIcon(:, :, 2))));
        corr3 = max(max(normxcorr2(fusedIcon(:, :, 3),charaIcon(:, :, 3))));
        corr = (corr1 + corr2 + corr3)/3;
        judgeGray(j) = corr;        
    end
    [r2,c2] = find(judgeGray == max(judgeGray));
    charaOnField{i+6} = charaNamesArr{c2};
end

end