context('test4', () => {

  beforeEach( ()=> {
    cy.visit('/');
  });

  it('should fail horribly again', () => {
    cy.get('h2').should('contain.text', 'xxx');
  });

  it('should pass (trivial)', () => {
    cy.get('h2').should('be.visible');
  });
});
