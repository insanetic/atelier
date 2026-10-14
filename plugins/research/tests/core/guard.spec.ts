import { test } from 'node:test'
import assert from 'node:assert/strict'
import { GUARDED_FILE, isGuardedWrite } from '../../core/guard.ts'

const F = 'research/studies/tax/findings.yaml'

test('writes into the tool-owned files are caught', () => {
  for (const command of [
    `echo x >> ${F}`,
    `cat new.yaml > ${F}`,
    `echo x | tee -a ${F}`,
    `sed -i '' 's/a/b/' ${F}`,
    `sed --in-place 's/a/b/' ${F}`,
    `perl -pi -e 's/a/b/' ${F}`,
    `yq -i '.[0].status = "current"' ${F}`,
    `rm ${F}`,
    `mv ${F} /tmp/old.yaml`,
    `truncate -s 0 ${F}`,
    `cp /tmp/old.yaml ${F}`,
    `git checkout -- ${F}`,
    'git restore research/studies/tax/assessment.yaml',
    `dd if=/dev/null of=${F}`,
    `python3 -c "import yaml; yaml.dump([], open('${F}', 'w'))"`,
    `node -e "require('fs').writeFileSync('${F}', '[]')"`,
  ]) assert.equal(isGuardedWrite(command), true, command)
})

test('reading and copying the files elsewhere stays allowed', () => {
  for (const command of [
    `cat ${F} | head`,
    `grep -n disputed ${F}`,
    `cp ${F} /tmp/backup.yaml`,
    `yq '.[] | .id' ${F}`,
    `sed -n '1,20p' ${F}`,
    `git diff -- ${F}`,
    `git log -p ${F}`,
    `python3 -c "import yaml; print(len(yaml.safe_load(open('${F}'))))"`,
    'echo x > research/studies/tax/study.md',
  ]) assert.equal(isGuardedWrite(command), false, command)
})

test('Edit and Write are guarded on the study files only', () => {
  assert.equal(GUARDED_FILE.test(`/repo/${F}`), true)
  assert.equal(GUARDED_FILE.test('/repo/research/studies/tax/study.yaml'), false)
  assert.equal(GUARDED_FILE.test('/repo/plugins/research/core/findings.ts'), false)
})
